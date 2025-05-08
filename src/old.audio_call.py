###################################################################################################
# LRECOMM
# AUTH: Luhar, Priyanshu [pluhar@csub.edu]
# CONT: 
# DATE: April 7, 2025
###################################################################################################


import os
import sys
import RNS
import LXMF
import time
import argparse
from datetime import datetime as dt

APP_NAME = "lrecomm"
ANNOUNCE_INTERVAL = 30
TARGET_HASH = ""

# This initialisation is executed when the program is started
def program_setup(configpath):
    # We must first initialise Reticulum
    reticulum = RNS.Reticulum(configpath)
    
    identity = RNS.Identity.from_file("my_identity")

    # Using the identity we just created, we create a my_destination.
    # Destinations are endpoints in Reticulum, that can be addressed
    # and communicated with. Destinations can also announce their
    # existence, which will let the network know they are reachable
    # and automatically create paths to them, from anywhere else
    # in the network.
    my_destination = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        APP_NAME,
        "yabadabadoo"
    )

    # We configure the my_destination to automatically prove all
    # packets addressed to it. By doing this, RNS will automatically
    # generate a proof for each incoming packet and transmit it
    # back to the sender of that packet. This will let anyone that
    # tries to communicate with the my_destination know whether their
    # communication was received correctly.
    my_destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
    
    # Everything's ready!
    # Let's hand over control to the announce loop
    announceLoop(my_destination)


def announceLoop(my_destination):
    # Let the user know that everything is ready
    RNS.log(
        "Announce Loop"+
        RNS.prettyhexrep(my_destination.hash)+
        " running, hit enter to manually send an announce (Ctrl-C to quit)"
    )

    # We enter a loop that runs until the users exits.
    # If the user hits enter, we will announce our server
    # my_destination on the network, which will let clients
    # know how to create messages directed towards it.
    while True:
        time.sleep(ANNOUNCE_INTERVAL)
        my_destination.announce()
        RNS.log("Sent announce from "+RNS.prettyhexrep(my_destination.hash))

def live_call(link):
     

##########################################################
#### Program Startup #####################################
##########################################################

# This part of the program gets run at startup,
# and parses input from the user, and then starts
# the desired program mode.
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Minimal example to start Reticulum and create a my_destination"
        )

        parser.add_argument(
            "--config",
            action="store",
            default=None,
            help="path to alternative Reticulum config directory",
            type=str
        )
        parser.add_argument(
            "destination",
            nargs="?",
            default=None,
            help="hexadecimal hash of the server destination",
            type=str
        )

        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        if (args.destination == None):
            print("")
            parser.print_help()
            print("")
        else:
            client(args.destination, configarg)
        
        program_setup(configarg)

    except KeyboardInterrupt:
        print("")
        sys.exit(0)
