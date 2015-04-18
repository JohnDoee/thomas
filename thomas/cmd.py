import argparse
import logging

from six.moves.urllib.parse import urlsplit

def commandline_handler():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_url", type=str, help='')
    parser.add_argument("-o", "--output_url", default='file://', type=str, help='', dest="output_url")
    parser.add_argument("--verbose", help="Increase output verbosity", action="store_true", dest="verbose")
    parser.add_argument("-s", "--segments", help="Number of segments to download with", type=int, default=6, dest="segments")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR,
                            format='%(asctime)-15s:%(levelname)s:%(name)s:%(message)s')
    
    parsed_input_url = urlsplit(args.input_url)
    parsed_output_url = urlsplit(args.output_url)
    
    if parsed_input_url.scheme in ['http', 'https']:
        from .input.http import HTTPInput
        inp = HTTPInput(parsed_input_url)
    
    size, filename = inp.get_piece_config()
    if not filename:
        filename = 'unknown-filename'
    
    if parsed_output_url.scheme in ['file', '']:
        from .output.file import FileOutput
        outp = FileOutput(parsed_output_url, filename, size)
    
    from .pieces import Pieces
    pieces = Pieces(size, args.segments)
    
    from .manager import Manager
    manager = Manager(inp, outp, pieces, args.segments)
    
    manager.start()