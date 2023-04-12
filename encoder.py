from src.module import EncodeHelper
import argparse

parser = argparse.ArgumentParser(description='Azur Lane Tachie Encoder')
parser.add_argument('chara', type=str, help='tachie to encode, eg. hailunna_h_rw')

if __name__ == '__main__':
    args = parser.parse_args().__dict__

    encoder = EncodeHelper(**args)
    encoder.encode()
