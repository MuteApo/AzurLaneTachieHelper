from src.module import ViewHelper
import argparse


parser = argparse.ArgumentParser(description='Azur Lane Tachie Viewer')
parser.add_argument('chara', type=str, help='tachie to view, eg. hailunna_h_rw')
parser.add_argument(
    '--win_width_enc', metavar='W', type=int,
    default=1440, help='display width of encoded image'
)
parser.add_argument(
    '--win_width_dec', metavar='W', type=int,
    default=1080, help='display width of decoded image'
)
parser.add_argument(
    '-p', '--padding', metavar='P', type=int, default=10, help='padding for image in window'
)
parser.add_argument(
    '--label_size', metavar='S', type=int, default=12, help='size of labels in bouding box'
)
parser.add_argument(
    '--label_color', metavar='C', type=int, nargs=4,
    default=[157, 41, 50, 196], help='RGBA color of labels in bouding box'
)
parser.add_argument(
    '--bbox_color', metavar='C', type=int, nargs=4,
    default=[217, 182, 18, 196], help='RGBA color of bouding box'
)
parser.add_argument('-l', '--logging', action='store_true', help='enable console logging')

if __name__ == '__main__':
    args = parser.parse_args().__dict__

    viewer = ViewHelper(**args)
    viewer.display(**args)
