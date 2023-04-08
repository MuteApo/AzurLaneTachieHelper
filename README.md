### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Decode & encode texture via file wavefront obj mesh
- Display bounding box with id on both textures for comparision

#### Components

- decoder.py
  - ```
    usage: decoder.py [-h] [-l] chara

    Azur Lane Tachie Decoder

    positional arguments:
      chara          tachie to decode

    options:
      -h, --help     show this help message and exit
      -l, --logging  enable console logging
    ```
  - Typical usage: `python decoder.py hailunna_h_rw`
  - Appointment:
    - encoded texture as `hailunna_h_rw-enc.png`
    - wavefront mesh as `hailunna_h_rw-mesh.obj`
    - decoded texture will written into `hailunna_h_rw-dec.png`

- encoder.py
  - ```
    usage: encoder.py [-h] -s S S [-l] chara

    Azur Lane Tachie Encoder

    positional arguments:
    chara                 tachie to encode

    options:
    -h, --help            show this help message and exit
    -s S S, --enc_size S S
                          size of encoded image
    -l, --logging         enable console logging
    ```
  - Typical usage: `python encoder.py hailunna_h_rw -s 2048 850`
  - Appointment:
    - Target size (width x height) is required to encode texture
    - Decoded texture as `hailunna_h_rw-dec.png`
    - Wavefront mesh as `hailunna_h_rw-mesh.obj`
    - Encoded texture will be written into `hailunna_h_rw-dec.png`

- viewer.py
  - ```
    usage: viewer.py [-h] [-we W] [-wd W] [-p P] [-ls S] [-lc C C C C] [-bc C C C C] [-l] chara

    Azur Lane Tachie Viewer

    positional arguments:
      chara                 tachie to view

    options:
      -h, --help            show this help message and exit
      -we W, --win_width_enc W
                            display Width of encoded image
      -wd W, --win_width_dec W
                            display Width of decoded image
      -p P, --padding P     padding for image in window
      -ls S, --label_size S
                            size of labels in bouding box
      -lc C C C C, --label_color C C C C
                            RGBA color of labels in bouding box
      -bc C C C C, --bbox_color C C C C
                            RGBA color of bouding box
      -l, --logging         enable console logging
    ```
    - Typical usage: `python viewer.py hailunna_h_rw -lc 255 0 0 196`
    - Appointment:
      - Encoded texture as `hailunna_h_rw-enc.png`
      - Decoded texture as `hailunna_h_rw-dec.png`
      - Wavefront mesh as `hailunna_h_rw-mesh.obj`
    - <img src="img/enc_view.png" width="640" />
    - <img src="img/dec_view.png" width="600" />

#### Requirements

- Python 3.8+ with following libraries:
  - PyGlet 2.0.5+
  - NumPy
  - Pillow
- Or run command:
  - ```shell
    pip install -r requirements.txt
    ```