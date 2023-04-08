from src.module import EncodeHelper
import argparse

parser = argparse.ArgumentParser(description='Azur Lane Tachie Encoder')
parser.add_argument('chara', type=str, help='tachie to encode')
parser.add_argument(
    '-s', '--enc_size', metavar='S', type=int, nargs=2,
    required=True, help='size of encoded image'
)
parser.add_argument('-l', '--logging', action='store_true', help='enable console logging')

if __name__ == '__main__':
    args = parser.parse_args().__dict__

    encoder = EncodeHelper(**args)
    encoder.encode(**args)
