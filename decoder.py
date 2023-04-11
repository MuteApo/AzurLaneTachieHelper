from src.module import DecodeHelper
import argparse

parser = argparse.ArgumentParser(description='Azur Lane Tachie Decoder')
parser.add_argument('chara', type=str, help='tachie to decode, eg. hailunna_h_rw')

if __name__ == '__main__':
    args = parser.parse_args().__dict__

    decoder = DecodeHelper(**args)
    decoder.decode()
