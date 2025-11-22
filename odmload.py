#!/bin/python3

import sys, os, time
import json
import argparse
import subprocess
from io import StringIO

from pathlib import Path
from tempfile import gettempdir
from dataclasses import dataclass

# Sensible defaults
tmpdir = Path(gettempdir())
loans_loc = tmpdir / 'libby-loans.json'
libby_loc = tmpdir / 'libby-cards.json'
config_loc = Path('odmpy-ng') / 'config' / 'config.json'

@dataclass
class Book:
    ID: int
    title: str
    site_id: int

@dataclass
class Card:
    name: str
    username: str
    site_id: int

def load_libby() -> tuple[list[Card], list[dict]]:
    # Run odmpy to get the data, check the return code
    res = subprocess.call(f'odmpy libby --exportloans {str(loans_loc)} --exportcards {str(libby_loc)}', shell=True)
    if res != 0:
        print(f"Error running odmpy libby: {res}")
        sys.exit(1)
    with open(libby_loc, 'r') as f:
        card_data = json.load(f)
    cards = [Card(name=c["advantageKey"], username=c["cardName"], site_id=int(c["library"]["websiteId"])) for c in card_data]
    with open(loans_loc, 'r') as f:
        loans = json.load(f)
    return cards, loans

def making_progress(tmp_folder: Path, dl_folder: Path, book: Book, verbose: bool = False, only_check_previous_run: bool = False) -> bool:
    progress = False
    if not tmp_folder.is_dir():
        return True
    if dl_folder.is_dir() and any(dl_folder.glob('*.mp3')):
        return True
    older_files = []
    older = tmp_folder / 'older.files'
    if older.is_file():
        with older.open('r') as f:
            older_files = f.read().splitlines()
    if only_check_previous_run:
        return len(older_files) > 0
    header = False
    for f in os.listdir(tmp_folder):
        if not f.endswith('.mp3') or f in older_files:
            continue
        if verbose:
            if not header:
                header = True
                print(f"Checking {book.title} for progress:")
            print(f"  {f}")
        older_files.append(f)
        progress = True
    if older_files:
        with older.open('w') as f:
            f.write('\n'.join(older_files))
    return progress

def build_docker(download_base: Path, tmp_base: Path) -> dict[str, str]:
    # Set up environment for docker run.
    UID = os.getuid()
    GID = os.getgid()

    env = os.environ.copy()
    env["HOST_UID"] = str(UID)
    env["HOST_GID"] = str(GID)
    env["AUDIOBOOK_FOLDER"] = str(download_base)
    env["AUDIOBOOK_TMP"] = str(tmp_base)
    env["COMPOSE_BAKE"] = "true"

    # Have odmpy-ng run build-compose.py to make its docker image.
    res = subprocess.check_output(f'./build-compose.py', shell=True, text=True, env=env, cwd='./odmpy-ng')
    lastline = res.splitlines()[-1]
    if not lastline.startswith('@'):
        print(f"Error running build-compose.py, output: {res}")
        sys.exit(1)
    env["SELENIUM_SHA"] = lastline

    return env

def generate_config(config_path: Path, cards: list[Card]):
    config = dict()
    if config_path.is_file():
        with config_path.open('r') as f:
            config = json.load(f)
        if not 'libraries' in config or not isinstance(config['libraries'], list):
            print(f"Error: config file {config_path} does not contain libraries list, is this an odmpy-ng config file?")
            sys.exit(1)
        print(f"Using existing config file {config_path} with {len(config)} options")
    config_example = config_path.parent / 'config.example.json'
    if not config_example.is_file():
        print(f"Error: config file {config_example} not found")
        sys.exit(1)
    with config_example.open('r') as f:
        config_baseline = json.load(f)
    added_options = 0
    del config_baseline['libraries']
    for key in config_baseline:
        if key not in config:
            added_options += 1
            config[key] = config_baseline[key]

    older = {lib['url'].lower():lib for lib in config['libraries']}
    config['libraries'] = libs = []
    unintialized = 'replace_this_with_quoted_pin'
    added_libraries = 0
    updated_libraries = 0
    for card in cards:
        lib = dict()
        name = card.name.lower()
        url = f'https://{name}.overdrive.com'.lower()
        suffix = name.split('-', 1)[-1] if '-' in name else None
        o = older.get(url)
        if o and 'pin' in o and o['pin'] != unintialized:
            lib = o
            del older[url]
            if 'site-id' not in lib or lib['site-id'] != card.site_id:
                updated_libraries += 1
                lib['site-id'] = card.site_id
            if suffix and not lib.get('subsite'):
                print(name, suffix)
                updated_libraries += 1
                lib['subsite'] = suffix
        else:
            added_libraries += 1
            lib['name'] = name
            if suffix:
                lib['subsite'] = suffix
            lib['url'] = url
            lib['card_number'] = card.username
            lib['pin'] = unintialized
            lib['site-id'] = card.site_id
        libs.append(lib)

    if older:
        print(f"WARNING: The following libraries are in the config file but not in libby: {', '.join(older.keys())}")
        # Add the older libraries so they don't get lost.
        libs.extend(older.values())

    if added_options or added_libraries or updated_libraries:
        encoded = json.dumps(config, indent=4)
        print(f"Generated config file with {len(config)-1} options and {len(libs)} libraries")
        print(f"{added_options} new options, {added_libraries} new libraries added, {updated_libraries} libraries given correct site-id")
        if unintialized in encoded:
            print(f"WARNING: Please edit {config_path} to replace {unintialized} with actual pin")
        with config_path.open('w') as f:
            f.write(encoded)
    else:
        print(f"Keeping existing config file {config_path} with {len(config)} options and {len(libs)} libraries")

def main():
    global libby_loc, loans_loc
    
    default_dest = os.getenv('AUDIOBOOK_FOLDER', None)
    default_tmp = os.getenv('AUDIOBOOK_TMP', None)

    # options
    args = argparse.ArgumentParser()
    args.add_argument(
        '-d', '--dest',
        type=str,
        default=default_dest,
        help=f'Directory under which files will be finally stored (default: AUDIOBOOK_FOLDER environment variable={default_dest})'
    )
    args.add_argument(
        '-t', '--tmp',
        type=str,
        default=default_tmp,
        help=f'Directory under which temporary files will be stored, AUDIOBOOK_TMP environment variable={default_tmp} will be used if not set'
    )
    # Add an optional argument to generate the odmpy-ng config file.
    args.add_argument('configure', type=str, help='supress run, generate odmpy-ng configuration instead', default=None, nargs='?')

    # parse
    opts = args.parse_args()

    cards, books = load_libby()

    if opts.configure is not None:
        print(f"Generating odmpy-ng configuration to file {opts.configure}")
        generate_config(Path(config_loc), cards)
        sys.exit(0)

    try:
        with open(config_loc, 'r') as f:
            ng_libraries = json.load(f)['libraries']
        site_ids = {lib['site-id'] for lib in ng_libraries if 'site-id' in lib}
    except ValueError:
        print(f"Error: odmpy-ng config file {config_loc} is not valid JSON or is missing fields, use 'odmload configure' to generate")
        sys.exit(1)

    if not site_ids:
        print(f"Error: odmpy-ng config file {config_loc} has no libraries with site-id, check whether Libby is configured and use 'odmload configure' to generate")
        sys.exit(1)

    if not books:
        print(f"No books checked out, nothing to do, exiting.")
        sys.exit(0)

    if not opts.dest:
        print("Error: no destination directory specified, use -d or AUDIOBOOK_FOLDER environment variable")
        sys.exit(1)
    if not opts.tmp:
        print("Error: no temporary directory specified, use -t or AUDIOBOOK_TMP environment variable")
        sys.exit(1)

    try:
        download_base = Path(opts.dest).absolute().resolve()
    except ValueError:
        print(f"Error: {opts.dest} is not a valid path")
        args.print_help()
        sys.exit(1)
    try:
        tmp_base = Path(opts.tmp).absolute().resolve()
    except ValueError:
        print(f"Error: {opts.dest} is not a valid path")
        args.print_help()
        sys.exit(1)

    libby_dest = download_base / 'libby'
    if not libby_dest.is_dir():
        print(f"Warning: libby path {libby_dest} is not a directory, attempting to create")
        libby_dest.mkdir(parents=True)

    # TODO: this doesn't display its output until complete, figure out why.
    # Note that the regular run DOES display, so I have a working solution.
    env = build_docker(download_base, tmp_base)

    unrecorded = []
    missing_books = []
    print(f"Scanning for needed books in {libby_dest} and {tmp_base}:")
    for item in books:
        ID = item['id']
        title = item['title']
        site_id = int(item['websiteId'])

        missing_books.append(site_id not in site_ids)
        if missing_books[-1]:
            print(f"WARNING: Book {ID} ({title}) has site-id {site_id} which is not in odmpy-ng config file {config_loc}")
            continue

        dir = libby_dest / ID
        if not dir.is_dir() or not any(dir.glob('*.mp3')):
            unrecorded.append(Book(ID, title, site_id))
        else:
            print(f"  {ID} - {title} ({site_id}) already in libby path")

    if unrecorded:
        print(f"---------------------------------------------------------------")

    IDs_in_tmp = {fn.name for fn in tmp_base.iterdir() if fn.is_dir()}
    IDs_in_both = {ID for ID in IDs_in_tmp if (final:=(libby_dest / ID)).is_dir() and any(final.glob('*.mp3'))}
    IDs_in_tmp -= IDs_in_both
    for book in unrecorded:
        tmp_folder = tmp_base / book.ID
        bad_marker = tmp_folder / 'bad'
        mp3s_text = (tmp_folder.is_dir() and len(set(tmp_folder.glob('*.mp3')))) or "no"
        if bad_marker.is_file():
            print(f"  {book.ID} - {book.title} ({book.site_id}) - in progress with {mp3s_text} mp3s found, marked bad but will keep trying.")
        else:
            print(f"  {book.ID} - {book.title} ({book.site_id}) - in progress with {mp3s_text} mp3s.")
        IDs_in_tmp.discard(book.ID)

    if IDs_in_tmp:
        print(f"---------------------------------------------------------------")
        # These are possibly expired from Libby checkout.
        # TODO: should download metadata first instead of waiting for whole book to be downloaded.
        for ID in IDs_in_tmp:
            tmp_folder = tmp_base / ID
            mp3s_text = len(set(tmp_folder.glob('*.mp3'))) or "no"
            print(f"  {ID} - no longer present in Libby data - {mp3s_text} mp3s, cannot continue.")

    if any(missing_books):
        print("site-ids:", site_ids)
        print(f"ERROR: odmpy-ng config file {config_loc} needs to be updated to include site-ids, run 'odmload configure'")
        # Make it a little more obvious if ALL of the books are unfetchable.
        if all(missing_books):
            sys.exit(2)

    if not unrecorded:
        print(f"{len(books)} checkedout books scanned but already present, nothing to do, exiting.")
        sys.exit(0)

    print(f"====================== Beginning run =======================")

    for book in unrecorded:
        print(f"\nRunning odmpy-ng for book: {book.title}")
        tmp_folder = tmp_base / book.ID
        dl_folder = download_base / 'libby' / book.ID

        was_previously_run = making_progress(tmp_folder, dl_folder, book, only_check_previous_run=True)
        res = -1
        # Using try/finally to handle things like ctrl-c. Include a timeout.
        out_buf = StringIO()
        start_time = time.time()
        proc = None

        try:
            # Stream output live and collect it
            proc = subprocess.Popen(f"docker compose run --rm odmpy-ng -s={book.site_id} -i={book.ID} -n=libby/{book.ID} -r",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                                cwd='./odmpy-ng', shell=True, text=True, env=env)
            if proc is None or proc.stdout is None or proc.stderr is None:
                print("Error downloading book {book.ID}, {book.title}: unable to start docker subprocess.")
                continue

            # Stream output in real time, so onlookers can see progress. Also
            # store in case of problems, or timeouts.
            for line in proc.stdout:
                out_buf.write(line)
                sys.stdout.write(line)
                sys.stdout.flush()
                # Handle timeout.
                elapsed = time.time() - start_time
                if elapsed > 60 * 30: # 30 minutes feels like enough!
                    stdout = proc.stdout.read() + '\n'
                    sys.stdout.write(stdout)
                    out_buf.write(stdout)
                    message = f"Timeout reached after {elapsed//60} minutes for book {book.ID}, killing process."
                    print(message)
                    out_buf.write(message + '\n')
                    if proc.poll() is None:
                        proc.kill()
                    break
        finally:
            # Collect stderr and cleanup proc.
            res = -1
            if proc is not None and proc.stdout is not None and proc.stderr is not None:
                stderr = proc.stderr.read() + '\n'
                sys.stdout.write(stderr)
                out_buf.write(stderr)
                proc.stderr.close()
                proc.stdout.close()
                res = proc.wait()
            else:
                print("Error downloading book {book.ID}, {book.title}: no subprocess started.")

            made_progress = making_progress(tmp_folder, dl_folder, book, verbose=True)
            if res != 0 or not made_progress:
                print(f"Error running odmpy-ng for book {book.ID}, {book.title}: {res} ",
                      ("no progress made" if not made_progress else ""))
                # Given an error, dump the log so we might see why.
                if not os.path.exists(tmp_folder):
                    tmp_folder.mkdir(parents=True)
                log = tmp_folder / 'process.log'
                with log.open('a') as f:
                    f.write(out_buf.getvalue() + '\n==================\n')
                # Allow two attempts to make progress, then give up.
                if was_previously_run and not made_progress:
                    badfile = tmp_folder / 'bad'
                    print("Marking tmp folder as bad, previous downloads made but no progress this time:", badfile)
                    badfile.touch()

if __name__ == '__main__':
    main()

