### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Easy drag & drop
- Decode & encode texture
- Merge & split paintingface 
- View bounding box comparision

#### Components (exemplified by `hailunna_h_rw`)

- `decoder.py`: extract and decode texture
- `encoder.py`: encode and replace texture
- `merger.py`: redirect paintingface to correct position
- `splitter.py`: clip off non-paintingface part
- `viewer.py`
  - ```
    usage: viewer.py [-h] [--win_width_enc W] [--win_width_dec W] [-p P] [--label_size S] [--label_color C C C C] [--bbox_color C C C C] [-l] chara

    Azur Lane Tachie Viewer

    positional arguments:
      chara                 tachie to view, eg. hailunna_h_rw

    options:
      -h, --help            show this help message and exit
      --win_width_enc W     display width of encoded image
      --win_width_dec W     display width of decoded image
      -p P, --padding P     padding for image in window
      --label_size S        size of labels in bouding box
      --label_color C C C C
                            RGBA color of labels in bouding box
      --bbox_color C C C C  RGBA color of bouding box
    ```
  - Run in default mode when drag and drop
  - Advanced options are limited to command line
  - Typical usage: `python viewer.py hailunna_h_rw --label_color 255 0 0 196`
  - <img src="img/enc_view.png" width="640" />
  - <img src="img/dec_view.png" width="640" />

#### File Organization (exemplified by `xinnong_2`)

- ```
  main folder/
  |--xinnong_2
  |--painting/
  |  |--xinnong_2_front_tex
  |  L--xinnong_2_tex
  L--paintingface/
     L--xinnong_2
  ```

#### Requirements

- Python 3.11+ with following libraries:
  - PyGlet 2.0.5+
  - NumPy
  - Pillow
  - UnityPy
  - (Optional) PyInstaller
- Or just run:
  - ```shell
    pip install -r requirements.txt
    ```