#!/usr/bin/env python
#
# a4crypt v0.9.0 last mod 2012/01/08
# Latest version at <http://github.com/ryran/a8crypt>
# Copyright 2011, 2012 Ryan Sawhill <ryan@b19.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#    General Public License <gnu.org/licenses/gpl.html> for more details.
#------------------------------------------------------------------------------
#
# TODO: SCRIPT docstring

from sys import stderr
from os import pipe, write, close
from shlex import split
from subprocess import Popen, PIPE
from collections import namedtuple
from getpass import getpass



class GpgInterface():
    """GPG/GPG2 interface for simple symmetric encryption/decryption.
    
    First thing: use subprocess module to call a gpg or gpg2 process, ensuring
    that one of them is available on the system; if not, of course we have to
    quit (raise exception). Either way, that's all for __init__.
    
    After that, it's up to you to call GpgInterface.launch_gpg(), giving it
    a passphrase, telling it whether you want encryption or decryption, and
    optionally passing it input and output filenames. See launch_gpg.__doc__ for
    details, but if you don't give filenames to launch_gpg(), you must first
    save your input to GpgInterface.inputdata; output goes to GpgInterface.stdout.
    
    Security: The launch_gpg() method takes a passphrase as an argument, but it
    never stores it on disk (not even in a tempfile); the passphrase is passed to
    gpg via an os file descriptor. Also, AES256 is used by default as the
    symmetric cipher algorithm for encryption (in contrast to GPG/GPG2's standard
    behavior of using CAST5), but this can be changed.
    
    List of StdLib modules/methods used and how they're expected to be named:
        from sys import stderr
        from os import pipe, write, close
        from shlex import split
        from subprocess import Popen, PIPE
    """
    
    
    def __init__(self, show_version=True):
        """Confirm we can run gpg or gpg2."""
        
        try:
            P = Popen(['gpg', '--version'], stdout=PIPE)
            gpgvers = P.communicate()[0]
            self.gpg = 'gpg --no-use-agent'
        except:
            try:
                P = Popen(['gpg2', '--version'], stdout=PIPE)
                gpgvers = P.communicate()[0]
                self.gpg = 'gpg2'
            except:
                stderr.write("This program requires either gpg or gpg2, neither "
                             "of which were found on your system.\n\n")
                raise
        
        # To show or not to show (gpg --version output)
        if show_version:
            stderr.write("{0}\n".format(gpgvers))
        
        # Class attributes
        self.inputdata = None   # Stores input text for launch_gpg()
        self.stdout = None      # Stores stdout stream from gpg subprocess
        self.stderr = None      # Stores stderr stream from gpg subprocess
        # Convert 'gpg --opts' or 'gpg2 --opts' to simply 'GPG' or 'GPG2'
        self.gpgupper = self.gpg[:4].upper().strip()
    
    
    def launch_gpg(self, mode, passphrase, in_file=None, out_file=None,
                   binarymode=False, cipher='aes256'):
        """Start our GPG/GPG2 subprocess & save or return its output.
        
        Aside from its arguments of a passphrase & a mode of 'en' for encrypt or
        'de' for decrypt, this method can optionally take an argument of two os
        filenames (for input and output). If these optional arguments are not
        used, input is read from GpgInterface.inputdata (which can contain normal
        non-list data).
        
        Whether reading from GpgInterface.inputdata or using filenames, this
        method saves the stdout and stderr streams from the gpg subpocess to
        GpgInterface.stdout & GpgInterface.stderr and returns retval, a boolean
        set by gpg's exit code. Additionally, gpg stderr is written to sys.stderr
        regardless of gpg exit code.
        
        Of lesser importance are the last two optional arguments.
        
        First, the  boolean argument of binarymode: defaults to False, which
        configures gpg to produce ASCII-armored output. A setting of True is only
        honored when operating in direct mode, i.e., when gpg is reading input
        from and saving output directly to files.
        
        Second, the str argument cipher: defaults to aes256, but other good
        choices would be cast5, twofish, camellia256. This arg corresponds to
        gpg's --cipher-algo, which defaults to cast5 & is case-insensitive.
        """
        
        # Sanity checking of arguments and input
        if mode not in {'en', 'de'}:
            stderr.write("Improper mode specified! Must be one of 'en' or 'de'.\n")
            raise Exception("Bad mode chosen")
        
        if in_file and not out_file:
            stderr.write("You specified {0!r} as an input file but you didn't "
                         "specify an output file.\n".format(in_file))
            raise Exception("Missing out_file")
        
        if in_file and in_file == out_file:
            stderr.write("Same file for both input and output, eh? Is it going "
                         "to work? NOPE. Chuck Testa.\n")
            raise Exception("in_file, out_file must be different")
        
        if not in_file and not self.inputdata:
            stderr.write("You need to save input to class attr 'inputdata' first. "
                         "Or specify an input file.\n")
            raise Exception("Missing input")
        
        if binarymode not in {True, False}:
            stderr.write("Improper binarymode value specified! Must be either "
                         "True or False (default: False).\n")
            raise Exception("Bad binarymode chosen")
        
        # Write our passphrase to an os file descriptor
        fd_in, fd_out = pipe()
        write(fd_out, passphrase) ; close(fd_out)
        
        # Set our encryption command
        if mode in 'en':
            
            # General encryption command, including ASCII-armor option
            cmd = ("{gpg} --batch --no-tty --yes --symmetric --force-mdc "
                   "--cipher-algo {algo} --passphrase-fd {fd} -a"
                   .format(gpg=self.gpg, algo=cipher, fd=fd_in))
            
            # If given filenames, add them to our cmd
            if in_file:
                
                # If binary mode requested, unset ASCII-armored output first
                if binarymode:
                    cmd = cmd[:-2]  # Removes the last two chars of cmd ('-a')
                cmd = ("{cmd} -o {fout} {fin}"
                       .format(cmd=cmd, fout=out_file, fin=in_file))
        
        # Set our decryption command
        elif mode in 'de':
            
            # General decryption command
            cmd = ("{gpg} --batch --no-tty --yes -d --passphrase-fd {fd}"
                   .format(gpg=self.gpg, fd=fd_in))
            
            # If given filenames, add them to our cmd
            if in_file:
                cmd = ("{cmd} -o {fout} {fin}"
                       .format(cmd=cmd, fout=out_file, fin=in_file))
        
        # If working with files directly ...
        if in_file:
            P = Popen(split(cmd), stdout=PIPE, stderr=PIPE)
        
        # Otherwise, need to pass 'inputdata' to stdin over PIPE
        else:
            P = Popen(split(cmd), stdin=PIPE, stdout=PIPE, stderr=PIPE)
        
        # Kick it off and save output for later
        self.stdout, self.stderr = P.communicate(input=self.inputdata)
        
        # How did it go?
        if P.returncode == 0:
            retval = True
        else:
            retval = False
        
        # Close fd, print stderr, return process output
        close(fd_in)
        stderr.write(self.stderr)
        return retval



class AFourCrypt:
    """Provide cmdline wrapper for symmetric {en,de}cryption functions of GPG.
    
    This simply aims to make GPG1/GPG2 symmetric ASCII encryption in terminals
    easier and more fun. (Actually, this was just an excuse for a project in my
    first week of learning python, but hey. ...)
    
    Instantiate this class with color=False if you like spam.
    
    The actual encryption and decryption is handled by the GpgInterface class.
    So all this really does is setup some pretty colors for terminal output,
    prompt for user input & passphrases, pass it all over to
    GpgInterface.launch_gpg(), and display the output. So see the docstring
    for that if you want more info about how the real work is done.
    """
    
    
    def __init__(self, color=True):
        """Decide GPG or GPG2 and define class attrs."""
        
        # Instantiate GpgInterface, which will check for gpg/gpg2
        self.gpgif = GpgInterface(show_version=False)
        
        # Set default symmetric encryption cipher algo
        self.cipher = 'AES256'
        
        # Color makes it a lot easier to distinguish input & output
        Colors = namedtuple('Colors', 'Z B p r b g c')
        if color:
            self.c = Colors(       # Zero, Bold, purple, red, blue, green, cyan
                Z='\033[0m', B='\033[0m\033[1m', p='\033[1;35m',
                r='\033[1;31m', b='\033[1;34m', g='\033[1;32m', c='\033[0;36m')
        else:
            self.c = Colors('', '', '', '', '', '', '')
    
    
    def test_rawinput(self, prompt, *args):
        """Test user input. Keep prompting until recieve one of 'args'."""
        prompt = self.c.B + prompt + self.c.Z
        userinput = raw_input(prompt)
        while userinput not in args:
            userinput = raw_input("{0.r}Expecting one of {args}\n{prompt}"
                                  .format(self.c, args=args, prompt=prompt))
        return userinput
    
    
    def get_multiline_input(self, EOFstr, keeplastline=False):
        """Prompt for (and return) multiple lines of raw input.
        
        Stop prompting once receive a line containing only EOFstr. Return input
        minus that last line, unless run with keeplastline=True.
        """
        userinput = []
        userinput.append(raw_input())
        while userinput[-1] != EOFstr:
            userinput.append(raw_input())
        if not keeplastline:
            userinput.pop()
        return "\n".join(userinput)
    
    
    def get_passphrase(self, confirm=True):
        """Prompt for a passphrase until user enters same one twice.
        
        Skip the second confirmation prompt if run with confirm=False.
        """
        while True:
            pwd1 = getpass(prompt="{b}Carefully enter passphrase:{Z} "
                                  .format(**self.c._asdict()))
            while len(pwd1) == 0:
                pwd1 = getpass(prompt="{r}You must enter a passphrase:{Z} "
                                      .format(**self.c._asdict()))
            if not confirm: return pwd1
            pwd2 = getpass(prompt="{b}Repeat passphrase to confirm:{Z} "
                                  .format(**self.c._asdict()))
            if pwd1 == pwd2: return pwd1
            print("{r}The passphrases you entered did not match!{Z}"
                  .format(**self.c._asdict()))
    
    
    def load_main(self):
        """Load initial prompt and kick off all the other functions."""
        
        GPG = self.gpgif.gpgupper
        # Banner/question
        print("{0.p}<{gpg}>".format(self.c, gpg=GPG)),
        print("{B}Choose: [{r}e{B}]ncrypt, [{r}d{B}]ecrypt, [{r}c{B}]ipher, "
              "or [{r}q{B}]uit{Z}".format(**self.c._asdict()))
        
        # Set mode with response to prompt
        mode = self.test_rawinput(": ", 'e', 'd', 'c', 'q')
        
        # QUIT MODE
        if mode in {'q', 'Q'}:
            
            if __name__ == "__main__":
                exit()
            return
        
        # CIPHER-SETTING MODE
        elif mode in 'c':
            
            print("{0.p}Set symmetric encryption cipher algorithm{0.Z}\n"
                  "Good choices: AES256, CAST5, CAMELLIA256, TWOFISH\n"
                  "Current setting: {0.r}{1}{0.Z} (gpg default: {0.r}CAST5{0.Z})\n"
                  "{0.p}Input new choice (case-insensitive) or Enter to cancel{0.B}"
                  .format(self.c, self.cipher))
            
            userinput = raw_input(": {0.Z}".format(self.c))
            if userinput:
                self.cipher = userinput
                print("encryption will be done with '--cipher-algo {0}'"
                      .format(userinput))
        
        # ENCRYPT MODE
        elif mode in 'e':
            
            # Get our message-to-be-encrypted from the user; save to variable
            print("{b}Type or paste message to be encrypted.\nEnd with line "
                  "containing only a triple-semicolon, i.e. {B};;;\n:{Z}"
                  .format(**self.c._asdict())),
            self.gpgif.inputdata = self.get_multiline_input(';;;')
            print
            
            # Get passphrase from the user
            passphrase = self.get_passphrase(confirm=True)
            
            # Launch our subprocess and print the output
            retval = self.gpgif.launch_gpg('en', passphrase, cipher=self.cipher)
            
            # If gpg succeeded, print output
            if retval:
                print("{0.g}\nEncrypted message follows:\n\n{0.c}{output}{0.Z}"
                      .format(self.c, output=self.gpgif.stdout))
            
            # Otherwise, user must have picked a bad cipher-algo
            else:
                print("{0.r}Looks like {gpg} didn't like the cipher-algo you "
                      "entered.\nChoose a different one.{0.Z}"
                      .format(self.c, gpg=GPG.lower()))
        
        # DECRYPT MODE
        elif mode in 'd':
            
            # Get our encrypted message from the user; save to variable
            print("{b}Paste gpg-encrypted message to be decrypted.\n{B}:{Z}"
                  .format(**self.c._asdict())),
            self.gpgif.inputdata = self.get_multiline_input(
                '-----END PGP MESSAGE-----', keeplastline=True)
            print
            
            # Get passphrase from the user
            passphrase = self.get_passphrase(confirm=False)
            
            # Launch our subprocess
            retval = self.gpgif.launch_gpg('de', passphrase)
            
            while True:
                
                # If gpg succeeded, print output
                if retval:
                    print("{0.g}\nDecrypted message follows:\n\n{0.c}{output}"
                          "{0.Z}\n".format(self.c, output=self.gpgif.stdout))
                    break
                
                # Otherwise, print error and give option to try again
                else:
                    print("{0.r}Error in decryption process! Try again with a "
                          "different passphrase?{0.Z}".format(self.c))
                    tryagain = self.test_rawinput("[y/n]: ", 'y', 'n')
                    if tryagain in 'n': break
                    passphrase = self.get_passphrase(confirm=False)
                    retval = self.gpgif.launch_gpg('de', passphrase)



# BEGIN
if __name__ == "__main__":

    from sys import argv
    if len(argv) == 2 and (argv[1] == '--nocolor' or argv[1] == '-n'):
        a4 = AFourCrypt(color=False)
    
    elif len(argv) == 1:
        a4 = AFourCrypt()
    
    else:
        print("Run with no arguments to get interactive prompt.\n"
              "Optional argument: --nocolor (alias: -n)")
        exit()
    
    while True:
        a4.load_main()
    
