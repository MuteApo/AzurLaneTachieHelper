### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Unpack & pack painting
- Merge & split paintingface 
- Support multi-layers
- Dump into photoshop document (i.e. psd)

#### File Organization (exemplified by `xinnong_2`)

- Before:
  ```
  main_folder/
  |--painting/
  |  |--xinnong_2_front_tex
  |  L--xinnong_2_tex
  |--paintingface/
  |  L--xinnong_2
  L--xinnong_2
  ```
- After:
  ```
  main_folder/
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

- Python 3.10 with following libraries:
  - NumPy
  - Pillow
  - Pytoshop
  - UnityPy
- Or with given env spec:
  - Conda
    ```shell
    conda env create -f environment.yml
    ```
  - Pypi
    ```shell
    pip install -r requirements.txt
    ```
- Build app
  - pyinstaller
    ```shell
    python build.py --pyinstaller/-p
    ```
  - nuitka (C++ compiler required, eg. msvc, gcc, clang, etc.)
    ```shell
    python build.py --nuitka/-n
    ```