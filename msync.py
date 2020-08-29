import argparse
import json
import os
import shutil
import socket
import zlib


def getcrc32(filepath):
    with open(filepath, "rb") as stream:
        buffr = stream.read(65535)
        value = 0
        while len(buffr) > 0:
            value = zlib.crc32(buffr, value)
            buffr = stream.read(65535)
    return format(value & 0xFFFFFFFF, "08x")


def request(directory, midpoint, mtime, size, crc32):

    if not os.path.isdir(directory):
        raise ValueError(f"'{directory}' is not a directory.")
    if not os.path.isdir(midpoint):
        raise ValueError(f"'{midpoint}' is not a directory.")

    data = {}
    data["name"] = os.path.basename(os.path.abspath(directory))
    data["rule"] = [mtime, size, crc32]
    data["stat"] = {}

    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            filerelp = os.path.relpath(filepath, directory)
            data["stat"][filerelp] = [
                os.path.getmtime(filepath),
                os.path.getsize(filepath),
                getcrc32(filepath) if crc32 else None,
            ]

    with open(os.path.join(midpoint, f"{data['name']}.msync"), "w") as f:
        json.dump(data, f)
    print(f"request file '{data['name']}.msync' created.")


def getupdate(stat, filerelp, filepath, mtime, size, crc32):
    if filerelp not in stat:
        return True
    if mtime and os.path.getmtime(filepath) < stat[filerelp][0]:
        return False
    if size and os.path.getsize(filepath) < stat[filerelp][1]:
        return False
    if crc32 and getcrc32(filepath) != stat[filerelp][2]:
        return True
    if not crc32 and os.path.getmtime(filepath) != stat[filerelp][0]:
        return True
    else:
        return False


def respond(request, directory):

    if not os.path.isfile(request):
        raise ValueError(f"'{request}' is not a file.")
    if not os.path.isdir(directory):
        raise ValueError(f"'{directory}' is not a directory.")

    with open(request, "r") as f:
        data = json.load(f)
    midpoint = os.path.dirname(request)
    os.remove(request)

    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            filerelp = os.path.relpath(filepath, directory)
            if getupdate(data["stat"], filerelp, filepath, *data["rule"]):
                print(f"copying '{filerelp}' ...")
                destpath = os.path.join(midpoint, data["name"], filerelp)
                os.makedirs(os.path.dirname(destpath), exist_ok=True)
                shutil.copy2(filepath, destpath)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="msync", description="synchronize directory through an intermediate storage device")
    subparsers = parser.add_subparsers()

    parser_req = subparsers.add_parser("request", help="request for DIRECTORY through MIDPOINT")
    parser_req.add_argument("DIRECTORY", type=str, help="the target local directory that requires updates")
    parser_req.add_argument("MIDPOINT", type=str, help="the common midpoint directory for file exchange")
    parser_req.add_argument("--mtime", action="store_true", help="update only if modify time is newer")
    parser_req.add_argument("--size", action="store_true", help="update only if file size is larger")
    parser_req.add_argument("--crc32", action="store_true", help="check difference using crc32 (default using mtime)")

    parser_res = subparsers.add_parser("respond", help="respond to a REQUEST with DIRECTORY")
    parser_res.add_argument("REQUEST", type=str, help="the request file generated by 'msync request'")
    parser_res.add_argument("DIRECTORY", type=str, help="the source local directory for providing updates")

    args = parser.parse_args()

    if hasattr(args, "MIDPOINT"):
        request(args.DIRECTORY, args.MIDPOINT, args.mtime, args.size, args.crc32)

    if hasattr(args, "REQUEST"):
        respond(args.REQUEST, args.DIRECTORY)

