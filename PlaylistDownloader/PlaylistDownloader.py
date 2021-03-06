import subprocess
import itertools
import os
import json
import regex
import multiprocessing
# multiprocessing.set_start_method('spawn', True)


class PlaylistDownloader(object):
    """
        
    :param workingFolder: The path to the folder all the intermediary data will be stored
    :type workingFolder: str
    :param mergedVideoFile: The path to where the output merged mkv will be placed
    :type mergedVideoFile: str
    :param videoFormats: The list of youtube-dl video formats that are accepted, in perference order. Newly uploaded videos may start in low quaility and then may later gain higher quality (this library doesn't redownload)
    :type videoFormats: [str]
    :param audioFormats:  The list of youtube-dl audio formats that are accepted, in perference order. Newly uploaded videos may start in low quaility and then may later gain higher quality (this library doesn't redownload)
    :type audioFormats: [str]
    :param playlist: The youtube playlist url
    :type playlist: str
    :param renameRegex: A regex used to generate chapter titles and order videos. It must have Number and Name capture groups. Videos are ordered by sorting the Number group as a float.
    :type renameRegex: regex
    :param trailerName: If the playlist has a trailer that doesn't follow normal naming convention it's filename should be specified here.
    :type trailerName: str, optional
    :param startSkip: The number of seconds to skip at the start of each video, defaults to 0
    :type startSkip: float, optional
    :param endSkip: The number of seconds to skip at the end of each video, defaults to 0
    :type endSkip: float, optional
    :param playlistStart: Which video to start downloading at, defaults to 1
    :type playlistStart: int, optional
    :param playlistEnd: Which video to stop downloading at, defaults to None
    :type playlistEnd: int, optional
    :param youtubeDLOptions: extra options to pass to youtube-dl, defaults to None
    :type youtubeDLOptions: array, optional
    """

    def __init__(self, workingFolder, mergedVideoFile, videoFormats, audioFormats, playlist, renameRegex, trailerName=None, startSkip=0, endSkip=0, playlistStart=1, playlistEnd=None, youtubeDLOptions=[]):
        self.workingFolder = workingFolder
        self.archiveFile = os.path.join(workingFolder, "progress")
        self.mergedProgressFile = os.path.join(workingFolder, "merged")
        self.downloadFolder = os.path.join(workingFolder, "downloads")
        self.convertFolder = os.path.join(workingFolder, "convert")
        self.trimmedFolder = os.path.join(workingFolder, "trimmed")
        self.renameFolder = os.path.join(workingFolder, "renamed")
        self.mergedVideoFile = mergedVideoFile
        self.videoFormats = videoFormats
        self.audioFormats = audioFormats
        self.playlist = playlist
        self.renameRegex = renameRegex
        self.trailerName = trailerName
        self.startSkip = startSkip
        self.endSkip = endSkip
        self.playlistStart = playlistStart
        self.playlistEnd = playlistEnd
        self.youtubeDLOptions = youtubeDLOptions


    def __getFormatString(self):
        return "/".join(map(lambda x: f'({x[0]}+{x[1]})', itertools.product(self.videoFormats, self.audioFormats)))

    def __runDownload(self):
        start = ["--playlist-start",
                 str(self.playlistStart)] if self.playlistStart != 1 else []
        end = ["--playlist-end", str(self.playlistEnd)
               ] if self.playlistEnd != None else []
        result = subprocess.run(["youtube-dl", "--download-archive", os.path.abspath(self.archiveFile),
                                 "--format", self.__getFormatString()] + start + end + self.youtubeDLOptions + [self.playlist], cwd=self.downloadFolder)
        result.check_returncode()

    def __getDownloadedFiles(self):
        filenames = os.listdir(self.downloadFolder)
        for name in filenames:
            if name.endswith(".part") or name.endswith(".ytdl"):
                continue
            yield {"filename": name, "path": os.path.join(self.downloadFolder, name), "convertPath": self.__getConvertOutputPath(name), "trimmedPath": self.__getTrimmedOutputPath(name)}

    def __getMediaFormat(self, path):
        process = subprocess.run(["ffprobe", "-show_entries", "stream=codec_name,codec_type",
                                  "-print_format", "json", path], capture_output=True)
        output = json.loads(process.stdout)
        result = {stream["codec_type"]: stream["codec_name"]
                  for stream in output["streams"]}
        return result

    def __getConvertOutputPath(self, name):
        outfileName = os.path.splitext(name)[0] + ".webm"
        output = os.path.join(self.convertFolder, outfileName)
        return output

    def __isFileConverted(self, filedata):
        return os.path.exists(filedata["convertPath"])

    # can't be made private otherwise name mangling would make multiprocessing unable to find it
    def _convert(self, fileData):
        media = self.__getMediaFormat(fileData["path"])
        if media["audio"] == "opus" and media["video"] == "vp9":
            os.symlink(os.path.relpath(
                fileData["path"], self.convertFolder), fileData["convertPath"])
        else:
            audioFlag = "copy" if media["audio"] == "opus" else "libopus"
            videoOptions = ["-vcodec", "copy"] if media["video"] == "vp9" else [
                "-vcodec", "libvpx-vp9", "-crf", "31", "-b:v", "0", "-row-mt", "1"]
            tempPath = fileData["convertPath"] + ".partial"
            subprocess.run(["ffmpeg", "-i", fileData["path"], "-f", "webm",
                            "-y", "-acodec", audioFlag] + videoOptions + [tempPath])
            os.rename(tempPath, fileData["convertPath"])

    def __getTrimmedOutputPath(self, name):
        outfileName = os.path.splitext(name)[0] + ".webm"
        output = os.path.join(self.trimmedFolder, outfileName)
        return output

    def __getFileDuration(self, path):
        process = subprocess.run(["ffprobe", "-show_entries", "format=duration",
                                  "-print_format", "json", path], capture_output=True)
        output = json.loads(process.stdout)
        return float(output["format"]["duration"])

    # can't be made private otherwise name mangling would make multiprocessing unable to find it
    def _trimIfNeeded(self, fileData):
        if os.path.exists(fileData["trimmedPath"]):
            return
        if self.startSkip == 0 and self.endSkip == 0:
            os.symlink(os.path.relpath(
                fileData["convertPath"], self.trimmedFolder), fileData["trimmedPath"])
            return
        startFlags = ["-ss", str(self.startSkip)] if self.startSkip != 0 else []
        endFlags = []
        if self.endSkip != 0:
            duration = self.__getFileDuration(fileData["convertPath"])
            endFlags = ["-to", str(duration - self.endSkip)]
        tempPath = fileData["trimmedPath"] + ".partial"
        subprocess.run(["ffmpeg", "-i", fileData["convertPath"]] + startFlags +
                       endFlags + ["-c", "copy", "-y", "-f", "webm", tempPath])
        os.rename(tempPath, fileData["trimmedPath"])

    def __rename(self, fileData):
        if fileData["filename"] == self.trailerName:
            rename = "0 - Trailer.webm"
            number = 0
        else:
            matches = regex.search(self.renameRegex, fileData["filename"])
            number = float(matches["Number"])
            rename = f'{matches["Number"]} - {matches["Name"]}.webm'
        output = os.path.join(self.renameFolder, rename)
        os.symlink(os.path.relpath(
            fileData["trimmedPath"], self.renameFolder), output)
        return {"name": rename, "path": output, "number": number}

    def __needToMerge(self, files):
        if(len(files) == 0):
            return False
        if not os.path.exists(self.mergedProgressFile):
            self.__recordMergeFinished([])
        with open(self.mergedProgressFile, "r") as file:
            seen = json.load(file)
            names = set(map(lambda x: x["name"], files))
            return names != set(seen)

    def __recordMergeFinished(self, files):
        names = list(map(lambda x: x["name"], files))
        with open(self.mergedProgressFile, "w") as file:
            json.dump(names, file)

    def __merge(self, files):
        paths = list(map(lambda x: x["path"], files))
        fileArgs = [paths.pop(0)]
        for path in paths:
            fileArgs.extend(["+", path])
        tempFile = self.mergedVideoFile + ".partial"
        subprocess.run(["mkvmerge", "--output", tempFile, "--webm", "--chapter-language", "eng",
                        "--generate-chapters-name-template", "<FILE_NAME>", "--generate-chapters", "when-appending"] + fileArgs)
        os.rename(tempFile, self.mergedVideoFile)
        self.__recordMergeFinished(files)

    def __setupFolders(self):
        os.makedirs(self.downloadFolder, exist_ok=True)
        os.makedirs(self.convertFolder, exist_ok=True)
        os.makedirs(self.trimmedFolder, exist_ok=True)
        os.makedirs(self.renameFolder, exist_ok=True)

    def run(self):
        """Starts the download/convert/trim/merge process
        """        
        self.__setupFolders()
        self.__runDownload()
        files = list(self.__getDownloadedFiles())
        toBeConverted = filter(
            lambda file: not self.__isFileConverted(file), files)
        with multiprocessing.Pool() as pool:
            pool.map(self._convert, toBeConverted)
            pool.map(self._trimIfNeeded, files)
        for file in os.listdir(self.renameFolder):
            os.remove(os.path.join(self.renameFolder, file))
        renamed = list(map(self.__rename, files))
        renamed.sort(key=lambda x: x["number"])
        if self.__needToMerge(renamed):
            self.__merge(renamed)
