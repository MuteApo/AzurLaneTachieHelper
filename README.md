### 碧蓝航线立绘助手 AzurLaneTachieHelper

#### Features

- Unpack/pack painting
- Merge/split paintingface
- Clip shipyardicon/herohrzicon/squareicon
- Support multiple layers
- Dump as photoshop document

#### Building Dependencies

- Python 3.10 with following libraries:
  - NumPy
  - Pillow
  - Pytoshop
  - UnityPy
- Or with given env spec:
  ```shell
  # Conda
  conda env create -f environment.yml

  # Pypi
  pip install -r requirements.txt
  ```
- Build app (C++ compiler required, eg. msvc, gcc, clang, etc.)
  ```shell
  python build.py
  ```