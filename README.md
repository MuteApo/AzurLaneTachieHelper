### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Decode & encode painting
- Merge & split paintingface 
- Support multi-layers
- Dump as photoshop document, aka psd

#### Components

- `decoder`: extract and decode painting & paintingface
- `encoder`: encode and replace painting & paintingface
- `viewer` (deprecated)

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
  |  L--xinnong_2
  |--xinnong_2
  L--xinnong_2.psd
  ```

#### Building Dependencies

- Python 3.8+ with following libraries:
  - NumPy
  - Pillow
  - Pytoshop
  - UnityPy
- Or just run
  - for Conda:
    ```shell
    conda env create -f environment.yml
    ```
  - for Pypi:
    ```shell
    pip install -r requirements.txt
    ```
- Build app by pyinstaller/nuitka:
  - ```shell
    python pack.py
    ```