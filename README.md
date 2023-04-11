### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Decode & encode texture via file wavefront obj mesh
- Display bounding box with id on both textures for comparision
- Merge & split paintingface with main texture
- Easy drag & drop tachie file on `.exe` executable
- Python environment is required to direct run on `.py`

#### Components

- decoder.py
  - ```
    usage: decoder.py [-h] [-l] chara

    Azur Lane Tachie Decoder

    positional arguments:
      chara          tachie to decode, eg. hailunna_h_rw

    options:
      -h, --help     show this help message and exit
    ```
  - Typical command line: `python decoder.py hailunna_h_rw`
  - Appointment:
    - Encoded texture as `hailunna_h_rw-enc.png`
    - Wavefront mesh as `hailunna_h_rw-mesh.obj`
    - Decoded texture will be written into `hailunna_h_rw-dec.png`

- encoder.py
  - ```
    usage: encoder.py [-h] -s S S [-l] chara

    Azur Lane Tachie Encoder

    positional arguments:
      chara                 tachie to encode, eg. hailunna_h_rw

    options:
      -h, --help            show this help message and exit
      -s S S, --enc_size S S
                            size of encoded image
    ```
  - Typical command line: `python encoder.py hailunna_h_rw`
  - Appointment:
    - Target size (width x height) is required, if original encoded texture cannot be found
    - Decoded texture as `hailunna_h_rw-dec.png`
    - Wavefront mesh as `hailunna_h_rw-mesh.obj`
    - Encoded texture will be written into `hailunna_h_rw-dec.png`

- viewer.py
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
  - Typical command line: `python viewer.py hailunna_h_rw --label_color 255 0 0 196`
  - Appointment:
    - Encoded texture as `hailunna_h_rw-enc.png`
    - Decoded texture as `hailunna_h_rw-dec.png`
    - Wavefront mesh as `hailunna_h_rw-mesh.obj`
  - <img src="img/enc_view.png" width="640" />
  - <img src="img/dec_view.png" width="640" />

- merger.py
  - ```
    usage: merger.py [-h] chara

    Azur Lane Tachie Merger

    positional arguments:
      chara       tachie to encode, eg. hailunna_h_rw

    options:
      -h, --help  show this help message and exit
    ```
  - Typical command line: `python merger.py hailunna_h_rw`
  - Appointment:
    - Tachie metadata as `hailunna_h_rw`, from `painting\` folder
    - Decoded texture as `hailunna_h_rw-dec.png`
    - Unpacked paintingface images as `paintingface\*.png`
    - Merged texture will be written into `paintingface-merge\*.png`

- splitter.py
  - ```
    usage: splitter.py [-h] chara

    Azur Lane Tachie Splitter

    positional arguments:
      chara       tachie to encode, eg. hailunna_h_rw

    options:
      -h, --help  show this help message and exit
    ```
  - Typical command line: `python splitter.py hailunna_h_rw`
  - Appointment:
    - Tachie metadata as `hailunna_h_rw`, from `painting\` folder
    - Tachie merged with paintingface as `paintingface-merge\*.png`
    - Splitted pantingface images will be written into `paintingface-split\*.png`


#### Requirements

- Python 3.8+ with following libraries:
  - PyGlet 2.0.5+
  - NumPy
  - Pillow
  - UnityPy
  - (Optional) PyInstaller
- Or just run:
  - ```shell
    pip install -r requirements.txt
    ```