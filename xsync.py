import argparse
import json
import os
import shutil
import zlib
from pathlib import Path


def getfile(localdir, midpoint):
    name = os.path.basename(os.path.abspath(localdir))
    for dirpath, dirnames, filenames in os.walk(localdir):
        for filename in filenames:
            lpath = os.path.join(dirpath, filename)
            token = os.path.relpath(lpath, localdir)
            rpath = os.path.join(midpoint, name, token)
            yield token, lpath, rpath


def getcrc32(lpath):
    with open(lpath, "rb") as stream:
        buffr = stream.read(33554432)
        value = 0
        while len(buffr) > 0:
            value = zlib.crc32(buffr, value)
            buffr = stream.read(33554432)
    return format(value & 0xFFFFFFFF, "08x")


def getstat(lpath, crc32):
    return (
        os.path.getmtime(lpath),
        os.path.getsize(lpath),
        getcrc32(lpath) if crc32 else None,
    )


def getupdate(stats, token, lpath, mtime, fsize, crc32):
    if token not in stats:
        return True
    if mtime and os.path.getmtime(lpath) < stats[token][0]:
        return False
    if fsize and os.path.getsize(lpath) < stats[token][1]:
        return False
    if crc32 and getcrc32(lpath) != stats[token][2]:
        return True
    if not crc32 and os.path.getmtime(lpath) != stats[token][0]:
        return True
    else:
        return False


def request(localdir, midpoint, mtime, fsize, crc32):

    if not os.path.isdir(localdir):
        raise ValueError(f"'{localdir}' is not a directory.")
    if not os.path.isdir(midpoint):
        raise ValueError(f"'{midpoint}' is not a directory.")

    data = {
        "rules": [mtime, fsize, crc32],
        "stats": {token: getstat(lpath, crc32) for token, lpath, rpath in getfile(localdir, midpoint)}
    }
    name = os.path.basename(os.path.abspath(localdir))
    xsyncreq = os.path.join(midpoint, f"{name}.xsync")

    Path(xsyncreq).write_text(json.dumps(data))
    print(f"request file '{xsyncreq}' created.")


def respond(xsyncreq, localdir):

    if not os.path.isfile(xsyncreq):
        raise ValueError(f"'{xsyncreq}' is not a file.")
    if not os.path.isdir(localdir):
        raise ValueError(f"'{localdir}' is not a directory.")

    midpoint = os.path.dirname(xsyncreq)
    data = json.loads(Path(xsyncreq).read_text())
    (mtime, fsize, crc32), stats = data["rules"], data["stats"]

    try:
        for token, lpath, rpath in getfile(localdir, midpoint):
            if getupdate(stats, token, lpath, mtime, fsize, crc32):
                print(f"copying '{token}' ...")
                os.makedirs(os.path.dirname(rpath), exist_ok=True)
                shutil.copy2(lpath, rpath)
                data["stats"][token] = getstat(lpath, crc32)
        os.remove(xsyncreq)
    except OSError:
        Path(xsyncreq).write_text(json.dumps(data))
        print(f"response incomplete, request file '{xsyncreq}' updated.")


def main():

    parser = argparse.ArgumentParser(prog="xsync", description="synchronize directory through an intermediate storage device")
    subparsers = parser.add_subparsers()

    parser_req = subparsers.add_parser("request", help="request for LOCALDIR through MIDPOINT")
    parser_req.add_argument("LOCALDIR", type=str, help="the target local directory that requires updates")
    parser_req.add_argument("MIDPOINT", type=str, help="the common midpoint directory for file exchange")
    parser_req.add_argument("-t", "--mtime", action="store_true", help="update only if modify time is newer")
    parser_req.add_argument("-s", "--fsize", action="store_true", help="update only if file size is larger")
    parser_req.add_argument("-c", "--crc32", action="store_true", help="check difference using crc32 (default using mtime)")

    parser_res = subparsers.add_parser("respond", help="respond to a XSYNCREQ with LOCALDIR")
    parser_res.add_argument("XSYNCREQ", type=str, help="the request file generated by 'xsync request'")
    parser_res.add_argument("LOCALDIR", type=str, help="the source local directory for providing updates")

    args = parser.parse_args()

    if hasattr(args, "MIDPOINT"):
        request(args.LOCALDIR, args.MIDPOINT, args.mtime, args.fsize, args.crc32)

    if hasattr(args, "XSYNCREQ"):
        respond(args.XSYNCREQ, args.LOCALDIR)


if __name__ == "__main__":

    main()