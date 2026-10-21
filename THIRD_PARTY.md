# Third-party components

[English](THIRD_PARTY.md) | [简体中文](THIRD_PARTY.zh-CN.md)

The source repository contains project scripts, the dependency lock, and copied upstream license texts. It does not include downloaded SPKs, decoder binaries, private NAS state, or generated media.

| Component | Source | Handling |
| --- | --- | --- |
| Initial thumbnail approach | https://github.com/Gitawake/synology-photos-server-side-thumbnailgen | MIT notice retained; see NOTICE.md |
| ImageMagick runtime | https://synocommunity.com/package/imagemagick | Lock contains official URL and SHA256; ImageMagick license alone does not cover every linked library |
| FFmpeg runtime | https://synocommunity.com/package/ffmpeg8 | Current binary enables GPL, version3 and nonfree; public binary distribution is blocked |
| Supporting shared libraries | https://synocommunity.com/package/synocli-videodriver | Only required library groups and their dependency closure are selected; component-by-component license and source audit remains required |
| Package recipes | https://github.com/SynoCommunity/spksrc | A recipe pointer is not a substitute for matching corresponding source |

During a personal build, ELF DT_RPATH/DT_RUNPATH entries are cleared so private library paths control resolution. ImageMagick's policy is replaced to disable delegates and restrict HEIC/JPEG modules. These modifications are implemented in tools/private_elf.py and src/photos_assistant/policy.xml. No vendor installation scripts are run, no system codec is replaced, and no hardware driver is installed.

The generated runtime-manifest.json records dependency URLs, SHA256, original package INFO, selected file counts, ELF changes and detected nonfree status. It is an inventory aid, not proof that every dependency is redistributable.

License texts under licenses/ are references, not a completed binary compliance bundle. See docs/distribution.md for the public release gate.

Primary references:

- https://www.ffmpeg.org/legal.html
- https://ffmpeg.org/doxygen/4.0/md_LICENSE.html
- https://imagemagick.org/license/

Project inspiration, upstream author attribution and dependency acknowledgements are documented in [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).
