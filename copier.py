#!/usr/bin/env python3

#Written by kelseykm

import sys
import readline
import glob
import os
import threading
import queue
import re

version = "0.2.9"
normal = "\033[0;39m"
red = "\033[1;31m"
green = "\033[1;32m"
orange = "\033[1;33m"
blue = "\033[1;34m"
stop_progress = False

class Reader:

    def __init__(self, infile_object):
        self.infile_object = infile_object
        self.chunk_size = 51200
        self.number_of_chunks = 0
        self.number_of_read_chunks = 0

    def number_chunks(self):
        file_size = os.stat(self.infile_object.name).st_size

        if file_size == 0:
            self.number_of_chunks = file_size
        elif file_size != 0 and file_size % self.chunk_size != 0:
            self.number_of_chunks = file_size // self.chunk_size + 1
        else:
            self.number_of_chunks = file_size/self.chunk_size

    def read_chunks(self):
        while True:
            chunk = self.infile_object.read(self.chunk_size)
            if not chunk:
                return
            yield chunk
            self.number_of_read_chunks += 1

class Copier:

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
        scandir_iter = os.scandir(file)
        for dir_entry in scandir_iter:
            if dir_entry.is_file():
                self.file_queue.put(dir_entry.path)
            elif dir_entry.is_dir():
                self.add_dirs(dir_entry.path)
                self.enum_dir(dir_entry.path)

    def add_dirs(self, directory):
        self.dir_set.add(directory)

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
        for directory in self.sorted_dirs:
            directory += "/"
            imp_dir = "/" + os.path.basename(self.file) + "/"
            destination = self.destination + imp_dir + directory.split(imp_dir)[-1]

            try:
                os.mkdir(destination)
                self.copy_stat(directory, destination)
            except FileExistsError:
                pass

    def copy_files(self, source, destination):

        print(f"{blue}[INFO]{normal} COPYING {orange}{source}{normal} TO {orange}{destination}{normal}")

        with open(source, "rb") as source_file, open(destination, "wb") as destination_file:
            global stop_progress
            stop_progress = False

            reader = Reader(source_file)

            reader.number_chunks()
            thread = threading.Thread(target=progress_status, args=(reader,))
            thread.start()

            try:
                for chunk in reader.read_chunks():
                    destination_file.write(chunk)

                thread.join()
                print(f"{blue}[INFO]{normal} COPYING DONE!")
            except Exception as raised_exception:
                stop_progress = True

                thread.join()
                print(f"{red}[ERROR]{normal} COPYING FAILED: {red}{raised_exception}{normal}")


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

def autocomplete(text, state):
    if "~" in text:
        text = re.sub(r"~", os.path.expanduser("~"), text)
    if os.path.isdir(text) and not text.endswith("/"):
        text += "/"
    return glob.glob(text + "*")[state]

def progress_status(reader):
    while True:
        if stop_progress or reader.number_of_chunks == reader.number_of_read_chunks:
            break
        sys.stdout.write(f"{blue}[INFO]{normal} [ {orange}{round(reader.number_of_read_chunks/reader.number_of_chunks*100, 1)}{normal} % ]")
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
    readline.set_completer_delims("\t")
    readline.parse_and_bind("tab: complete")
    readline.set_completer(autocomplete)

    if not sys.argv[1:] or not sys.argv[1] in ["-c", "-h", "--help", "-t", "-v", "--version"]:
        usage()
    elif sys.argv[1] in ["-h", "--help", "-v", "--version"] and sys.argv[2:]:
        usage()
    elif not sys.argv[2:] and sys.argv[1] in ["-c", "-t"]:
        usage()

    if sys.argv[1] == "-h" or sys.argv[1] == "--help":
        usage()
    elif sys.argv[1] == "-v" or sys.argv[1] == "--version":
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

        if not os.path.isfile(files):
            print(f"{red}[ERROR]{normal} {files} IS NOT A REGULAR FILE")
            sys.exit()

        with open(files) as file_paths:
            infiles = [ os.path.abspath(file.strip()) for file in file_paths.readlines() ]

        error = False
        for file in infiles:
            if not os.path.exists(file):
                print(f"{red}[ERROR]{normal} {file} DOES NOT EXIST")
                error = True
        if error:
            sys.exit()

        for file in infiles:
            copier = Copier(os.path.abspath(file), dst)
            copier.check_type()
            copier.make_dirs()
            copier.copier()
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
            copier = Copier(os.path.abspath(file), dst)
            copier.check_type()
            copier.make_dirs()
            copier.copier()

if __name__ == "__main__":
    main()
