{ nixpkgs ? import <nixpkgs> { } }:
let
  inherit (nixpkgs) pkgs;
  inherit (pkgs) python3Packages;

  pythonDeps = ps:
    with ps; [
      #runtime dep
      regex

      #docs
      sphinx_rtd_theme
      sphinx

      #formatting
      pylint
      autopep8
    ];

  python = pkgs.python38.withPackages pythonDeps;
  nixPackages = [ python pkgs.ffmpeg pkgs.mkvtoolnix pkgs.youtube-dl ];
in pkgs.stdenv.mkDerivation {
  name = "playlistDownloader-workspace";
  buildInputs = nixPackages;
}
