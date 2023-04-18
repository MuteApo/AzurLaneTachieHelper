### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Easy drag & drop
- Decode & encode texture
- Mark corresponding bounding box
- Merge & split paintingface 
- Support multi-layer tachies
- Combine layers as psd

#### Components (exemplified by `hailunna_h_rw`)

- `decoder.py`: extract and decode texture, combine to psd file
- `encoder.py`: encode and replace texture
- `merger.py`: reposition paintingface on painting, combine to psd file
- `splitter.py`: clip off non-paintingface part from whole painting
- `viewer.py`
  - ```shell
    usage: viewer.py [-h] [--label_size S] [--label_color C C C C] [--bbox_color C C C C] chara

    Azur Lane Tachie Viewer

    positional arguments:
      chara                 tachie to view, eg. hailunna_h_rw

    options:
      -h, --help            show this help message and exit
      --label_size S        size of labels in bounding box
      --label_color C C C C
                            RGBA color of labels in bounding box
      --bbox_color C C C C  RGBA color of bounding box
    ```
  - Run in default mode when drag and drop
  - Advanced options are limited to command line
  - Typical usage: `python viewer.py hailunna_h_rw --label_color 255 0 0 196`
  - <img src="img/enc_view.png" width="640" />
  - <img src="img/dec_view.png" width="640" />

#### File Organization (exemplified by `xinnong_2`)

- Before:
  ```
  main folder/
  |--painting/
  |  |--xinnong_2_front_tex
  |  L--xinnong_2_tex
  |--paintingface/
  |  L--xinnong_2
  L--xinnong_2
  ```
- After:
  ```
  main folder/
  |--output/
  |  |--painting/
  |  |  |--xinnong_2_front_tex
  |  |  L--xinnong_2_tex
  |  L--paintingface/
  |     L--xinnong_2
  |--painting/
  |  |--xinnong_2_front_tex
  |  L--xinnong_2_tex
  L--paintingface/
  |  |--diff/
  |  |  |--1.png
  |  |  |--2.png
  |  |  |--3.png
  |  |  |--4.png
  |  |  |--5.png
  |  |  L--6.png
  |  L--xinnong_2
  |--xinnong_2
  |--xinnong_2_front-mesh.obj
  |--xinnong_2_mesh.obj
  |--xinnong_2_front-dec.png
  |--xinnong_2_front-enc.png
  |--xinnong_2-dec.png
  |--xinnong_2-enc.png
  L--xinnong_2.psd
  ```

#### Building Requirements

- Python 3.8+ with following libraries:
  - PyGlet
  - NumPy
  - Pillow
  - Pytoshop
  - UnityPy
  - Pyinstaller
- Or just run
  - for Conda:
    ```shell
    conda env create -f environment.yml
    ```
  - for Pypi:
    ```shell
    pip install -r requirements.txt
    ```
- Build by spec given:
  - ```shell
    pyinstaller app.spec
    ```