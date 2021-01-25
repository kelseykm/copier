#!/usr/bin/env python3

#Written by kelseykm

import sys
import readline
import glob
import os
import threading
import queue

version = 0.2
normal = "\033[0;39m"
red = "\033[1;31m"
green = "\033[1;32m"
orange = "\033[1;33m"
blue = "\033[1;34m"

class Copier(object):

    def __init__(self, infile_object):
        self.infile_object = infile_object
        self.chunk_size = 51200
        self.number_of_chunks = 0
        self.number_of_read_chunks = 0

    def number_chunks(self):
        file_size = os.stat(self.infile_object.name).st_size

        x = file_size/self.chunk_size
        if type(x) is float:
            self.number_of_chunks = x.__floor__() + 1
        else:
            self.number_of_chunks = x

    def read_chunks(self):
        while True:
            chunk = self.infile_object.read(self.chunk_size)
            if not chunk:
                return
            yield chunk
            self.number_of_read_chunks += 1

class Sorter(object):

    def __init__(self, file, destination):
        self.file = file
        self.destination = destination
        self.file_queue = queue.Queue()
        self.dir_set = set()

    def check_type(self):
        if os.path.isfile(self.file):
            self.add_file(self.file)
        elif os.path.isdir(self.file):
            self.add_dirs(self.file)
            self.enum_dir(self.file)

    def enum_dir(self, file):
        gen_ob = os.scandir(file)
        for f in gen_ob:
            if f.is_file():
                self.file_queue.put(f.path)
            elif f.is_dir():
                self.add_dirs(f.path)
                self.enum_dir(f.path)

    def add_dirs(self, dir):
        self.dir_set.add(dir)

    def add_file(self, file):
        self.file_queue.put(file)

    def sort_dirs(self):
        self.sorted_dirs = sorted(self.dir_set)

    def copy_stat(self, source, destination):
        stats = os.stat(source)

        #copy access and modified times
        os.utime(destination, (stats.st_atime,stats.st_mtime))

        #copy owner and group
        os.chown(destination, stats.st_uid, stats.st_gid)

        #copy permission bits
        os.chmod(destination, stats.st_mode)

    def make_dirs(self):
        self.sort_dirs()
        for dir in self.sorted_dirs:
            imp_dir = os.path.basename(self.file)
            complete_destination = self.destination + "/" + imp_dir + dir.split(imp_dir)[-1]

            try:
                os.mkdir(complete_destination)
                self.copy_stat(dir, complete_destination)
            except FileExistsError:
                pass

    def copy_files(self, source, destination):

        print(f"{blue}[INFO]{normal} COPYING {orange}{source}{normal} TO {orange}{destination}{normal}")

        with open(source, "rb") as s, open(destination, "wb") as d:
            c_obj = Copier(s)

            c_obj.number_chunks()
            thread = threading.Thread(target=progress_status, args=(c_obj,))
            thread.start()

            for chunk in c_obj.read_chunks():
                d.write(chunk)

            thread.join()
            print(f"{blue}[INFO]{normal} COPYING DONE!")

    def copier(self):
        while True:
            if self.file_queue.empty():
                break

            file = self.file_queue.get()

            if os.path.isdir(self.file):
                imp_dir = "/" + os.path.basename(self.file) + "/"
                destination = self.destination + imp_dir + file.split(imp_dir)[-1]
            elif os.path.isfile(self.file):
                destination = self.destination + "/" + os.path.basename(file)

            self.copy_files(file, destination)
            self.copy_stat(file, destination)

class Autocomplete(object):

    def autocomplete_path(self, text, state):
        line = readline.get_line_buffer().split()
        if "~" in text:
            text = os.path.expanduser("~")
        if os.path.isdir(text):
            text += "/"
        return [x for x in glob.glob(text + "*")][state]

def progress_status(c_obj):
    while True:
        if c_obj.number_of_chunks == c_obj.number_of_read_chunks:
            break
        sys.stdout.write(f"{blue}[INFO]{normal} [ {orange}{round(c_obj.number_of_read_chunks/c_obj.number_of_chunks*100, 1)}{normal} % ]")
        sys.stdout.write("\r")
        sys.stdout.flush()

def usage():
    instructions = """
Usage: copier.py [option] [ <file paths> | <text file with file paths> ]

Python utility for copying files or directories

Options:
    -c  if this option is used, the paths of the files to be copied will be added
        on the commandline after the option. Useful when only copying 1 or 2 files

    -t  if this option is used, the paths of the files to be copied are put in a
        text file, and the path of the text file is added on the commandline after the option.
        Useful when copying many files.

    -h, --help      Show usage

    -v, --version   Show version number

NB: You will be prompted for the destination

Examples:
1) copier.py -c /path/to/file/1 /path/to/file/2 ../path/to/file/3
2) copier.py -t /path/to/text/file/with/paths
"""
    print(instructions)
    sys.exit()

def main():
    t = Autocomplete()
    readline.set_completer_delims("\t")
    readline.parse_and_bind("tab: complete")
    readline.set_completer(t.autocomplete_path)

    if sys.argv[1].startswith("-c") or sys.argv[1].startswith("-t") or sys.argv[1].startswith("-h") or sys.argv[1].startswith("-v"):
        pass
    else:
        usage()

    if sys.argv[1] == "-h":
        usage()
    elif sys.argv[1] == "-v":
        print(f"{blue}[INFO]{normal} VERSION {orange}{version}{normal}")
        sys.exit()

    dst = input(f"{green}[INPUT]{normal} ENTER DESTINATION FOLDER: ")
    while True:
        if os.path.exists(dst) and os.path.isdir(dst):
            break
        else:
            print(f"{red}[ERROR]{normal} INVALID INPUT: {orange}{dst}{normal}")
            dst = input(f"{green}[INPUT]{normal} ENTER DESTINATION FOLDER: ")
    dst = os.path.abspath(dst)

    if sys.argv[1] == "-t":
        files = sys.argv[2]
        if not os.path.exists(files):
            print(f"{red}[ERROR]{normal} {files} DOES NOT EXIST")
            sys.exit()

        with open(files) as f:
            infiles = [ os.path.abspath(file.strip()) for file in f.readlines() ]

        error = False
        for file in infiles:
            if not os.path.exists(file):
                print(f"{red}[ERROR]{normal} {file} DOES NOT EXIST")
                error = True
        if error:
            sys.exit()

        for file in infiles:
            obj = Sorter(os.path.abspath(file), dst)
            obj.check_type()
            obj.make_dirs()
            obj.copier()
    elif sys.argv[1] == "-c":
        files = sys.argv[2:]

        error = False
        for file in files:
            if not os.path.exists(file):
                print(f"{red}[ERROR]{normal} {file} DOES NOT EXIST")
                error = True
        if error:
            sys.exit()

        for file in files:
            obj = Sorter(os.path.abspath(file), dst)
            obj.check_type()
            obj.make_dirs()
            obj.copier()

if __name__ == "__main__":
    main()
