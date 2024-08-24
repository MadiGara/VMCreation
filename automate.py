#!/usr/bin/env python3

# Madison Gara

from datetime import datetime
import shutil
import A2functions as a2f
import os

# read the files azure.conf and gcp.conf, if they exist, use to create VMs
def read_config(config_name):

    if config_name == "azure.conf":
        success = a2f.get_azure_fields()
        if success == False:
            print("Error: Azure expected fields missing or incorrect in at least one VM.")
            print("Please ensure variables include the accepted configuration variables marked MANDATORY in the ReadMe, as well as the red configuration variables for Azure on the A2YY assignment description.")
            return 1
        
    elif config_name == "gcp.conf":
        success = a2f.get_gcp_fields()
        if success == False:
            print("Error: Azure expected fields missing or incorrect in at least one VM.")
            print("Please ensure variables include the accepted configuration variables marked MANDATORY in the ReadMe, as well as the red configuration variables for GCP on the A2YY assignment description.")
            return 1

    else:
        print("Error: Only azure.conf and gcp.conf config files, or quit or exit commands, are accepted (case-sensitive).")
        return 1
    
    return 0


# executor function, chooses config type and carries out operations accordingly
def main():
    # allow user config name input
    print("\nNOTE: The shell will run until \"quit\" or \"exit\" is entered as the configuration file name.")
    while True:
        print("\nPlease enter the name of the configuration file you'd like to use:")
        config_name = input()
        if config_name == "exit" or config_name == "quit":
            return
        else:
            read_config(config_name)

        datestamp = str(datetime.now())
        datestamp = (datestamp.split("."))[0]
        datestamp = datestamp.replace(" ", ":")

        if config_name == "azure.conf":
            filename = "azure_" + datestamp + ".conf"
            shutil.copy("azure.conf", filename)
            # as per professor Yan February 13th, delete original config after transferrance
            os.remove("azure.conf")
        elif config_name == "gcp.conf":
            filename = "gcp_" + datestamp + ".conf"
            shutil.copy("gcp.conf", filename)
            # as per professor Yan February 13th, delete original config after transferrance
            os.remove("gcp.conf")


if __name__ == "__main__":
    main()
