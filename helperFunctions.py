#!/usr/bin/env python3

# Madison Gara

import configparser
import subprocess
from datetime import datetime
import json
import re
import time

# get Azure config file details to create a VM and log file from them
def get_azure_fields():
    config = configparser.ConfigParser()
    config.read("azure.conf")
    num = 1
    read = False

    # get datetime and set up output txt file
    datestamp = str(datetime.now())
    datestamp = (datestamp.split("."))[0]
    datestamp = datestamp.replace(" ", ":")

    filename = "VMcreationAZ_" + datestamp + ".txt"
    file = open(filename, 'a')
    file.write("Date Stamp: " + datestamp + "\n")
    # get from shell metadata as per professor Yan
    user = subprocess.run('whoami', universal_newlines=True, capture_output=True)
    user = user.stdout
    file.write("System Admin Name: " + user + "\n")

    while num != 10:
        vm = "azure" + (str(num)).zfill(2)
        try:
            # get list of fields in the config file
            fields = []
            for key,value in config.items(vm):
                fields.append(key)

            # required fields for VM creation
            name = config[vm]['name']
            resource_group = config[vm]['resource-group']
            image = config[vm]['image']
            # required for my purposes, but not needed in creation
            if "os" in fields:
                ops = config[vm]['os']
            else:
                if (("Win" in image) or ("win" in image)):
                    ops = "windows"
                else:
                    ops = "linux"
            # back to required
            location = config[vm]['location']
            admin_username = config[vm]['admin-username']
            authentication = config[vm]['authentication-type']
            if (authentication == "ssh" or authentication == "all") and ops == "windows":
                authentication = "password"
            priority = config[vm]['priority']

            # only required for windows and all/password authentification
            if ops == "windows" or authentication == "password" or authentication == "all":
                admin_password = config[vm]['admin-password']
            else:
                admin_password = "default"

            # only required if user specifies them 
            if "open-ports" in fields:
                port = config[vm]['open-ports']
            else:
                port = "443"
            if "port-priority" in fields:
                port_priority = config[vm]['port-priority']
            else:
                port_priority = 100
            
            num += 1
            read = True
            print("\nName:", name) # for clarity

            # check if resource group exists, create it if not
            print("Command (check if a resource group exists): az group exists -n", resource_group)
            result = subprocess.run(['az', 'group', 'exists', '-n', resource_group],\
                        universal_newlines = True, capture_output = True)
            print("Resource group", resource_group, "exists:", (result.stdout).strip())
            if (result.stdout).strip() == "false":
                print("Command (create nonexistant resource group): az group create -l", location, "-n", resource_group)
                result = subprocess.run(['az', 'group', 'create', '-l', location, '-n', resource_group])
                if result.returncode != 0:
                    return 1
                else:
                    print("New resource group", resource_group, "created successfully.")

            if ops == "windows" or authentication == "password" or authentication == "all":   
                # verify that admin password is of valid format with regex
                num_conditions_met = pwd_check_regex(admin_password)
                if (len(admin_password) < 12) or (len(admin_password) > 123):
                    print("Error: Your admin-password in azure.conf for VM", name, "must be between 12 and 123 characters in length. Please change the configuration file and run again.")
                    return False
                elif (num_conditions_met < 3):
                    print("Error: Your admin-password in azure.conf for VM", name, "must contain at least 3 of the following: lowercase letters, uppercase letters, numbers, and special characters.")
                    print("Please change the configuration file and run again.")
                    return False
            
            # create VM itself
            success = create_azure_VM(fields, port, port_priority, name, resource_group, image, location, admin_username, admin_password, authentication, priority)

            if success == 0:
                # get VM status (powerState) - give it time to process
                time.sleep(2)
                print("Command (get VM status): az vm show -g", resource_group, "-n", name, "-d --query powerState")
                result = subprocess.run(['az', 'vm', 'show', '-g', resource_group, '-n', name, '-d', '--query', 'powerState'],\
                                        universal_newlines = True, capture_output = True)
                print(result.stdout)
                powerState = (result.stdout).replace("\"","")
                type = "Azure"
                
                # output VM details to file (for each vm)
                write_txt(fields, type, file, config, vm, name, ops, image, location, powerState)
        except:
            break
    
    file.close()
    return read


# create azure VM from config fields
def create_azure_VM(fields, port, port_priority, name, resource_group, image, location, admin_username, admin_password, authentication, priority):
    # password used
    args1 = ['az','vm','create',\
            '--resource-group',resource_group,\
            '--location',location,\
            '--name',name,\
            '--image',image,\
            '--admin-username',admin_username,\
            '--admin-password',admin_password,\
            '--authentication-type',authentication,\
            '--priority',priority,\
            '--generate-ssh-keys',\
            '--verbose',\
            '--no-wait']
    command1 = ""
    for arg in args1:
        command1 = command1 + arg + " "

    # password not used
    args2 = ['az','vm','create',\
            '--resource-group',resource_group,\
            '--location',location,\
            '--name',name,\
            '--image',image,\
            '--admin-username',admin_username,\
            '--authentication-type',authentication,\
            '--priority',priority,\
            '--generate-ssh-keys',\
            '--verbose',\
            '--no-wait']
    command2 = ""
    for arg in args2:
        command2 = command2 + arg + " "

    # check that additional config variables are acceptable
    if authentication != "password" and authentication != "ssh" and authentication != "all":
        print("Error: The authentication-type configuration variable can only take all, password, or ssh as values.")
        return 1
    if priority != "Regular":
        if (priority == "Spot") or (priority == "Low"):
            print("WARNING: VMs with priorities that are not set to Regular wait until resources are available in Azure to create, and as such may take a very long time to do so. Please see the Warning section of the ReadMe for further details.")
        else:
            print("Error: The priority configuration variable can only take Regular, Low, or Spot as values.")
            return 1

    # password not used
    if authentication == "ssh":    
        print("Command: " + command2 + "\nAre you okay with executing the creation of this VM? y/n")
    # password used
    else:
        print("Command: " + command1 + "\nAre you okay with executing the creation of this VM? y/n") 
    response = input()
    if response == "y":
        # check if the image exists
        print("Command (check if image exists): az vm image list --location", location, "-o json")
        result = subprocess.run(['az','vm','image','list','--location',location,'-o','json'], universal_newlines=True, capture_output=True)
        output = result.stdout
        print(output)
        data = json.loads(output)
        images = [item['urnAlias'] for item in data]
        if image not in images:
            print(result.stdout)
            print("Error: Image", image, "does not exist in location", location, "so exiting this VM.")
            return 1
        
        if authentication == "ssh":
            print("Command (create VM):", command2)
            result = subprocess.run(args2)
        else:
            print("Command (create VM):", command1)
            result = subprocess.run(args1)

        # VM exists error likely
        if result.returncode != 0:
            try:
                print("Command (check if VM already exists): az vm show --resource-group", resource_group, "--name", name, "-o table")
                result = subprocess.run(['az', 'vm', 'show', '--resource-group', resource_group, '--name', name, '-o', 'table'],\
                                         universal_newlines = True, capture_output=True)
                if result.returncode == 0:
                    print(result.stdout)
                    print("VM already exists.")
                    return 1
                else:
                    print("Error encountered while creating the VM.")
                    print(result.stdout)
                    return 1
            except:
                print("Error encountered while checking if the VM exists.")
                print(result.stdout)
                return 1
            
        # VM created or duplicate ignored successfully
        else:  
            # check it doesn't exist already
            try:
                print("Command (check if VM already exists): az vm show --resource-group", resource_group, "--name", name, "-o table")
                result = subprocess.run(['az', 'vm', 'show', '--resource-group', resource_group, '--name', name, '-o', 'table'],\
                                            universal_newlines = True, capture_output=True)
                if result.returncode == 0:
                    print(result.stdout)
                    print("VM already exists.")
                    return 1
                else:
                    print("VM does not yet exist!")

                # port dealings if specified in config file
                if "open-ports" in fields:
                    # sleep before opening port to allow vm time to create
                    print("Allowing the VM 10 seconds to create before opening the port.")
                    time.sleep(10)

                    if int(port_priority) < 100 or int(port_priority) > 4096:
                        print("Error: Port priority number must be between 100 and 4096. Exiting this VM's creation.")
                        return 1
                    ports = port.split(",")
                    for item in ports:
                        if int(item) != 443 and int(item) != 80:
                            print("Error: Only ports 443 or 80 are accepted.")
                            return 1
                        
                    # open designated ports from .conf and assign priority, commented out for brevity
                    print("\nOpening .conf designated ports, please stand by.")
                    try:
                        print("Command (open port): az vm open-port -n", name, "-g", resource_group, "--port", port,"--priority",port_priority)
                        result = subprocess.run(['az','vm','open-port','-n',name,'-g',resource_group,'--port',port,'--priority',port_priority])
                        if result.returncode != 0:
                            return 1
                        else:
                            # prints output automatically because not piped
                            return 0
                    except:
                        print("Error: Open port", port, "failed to run.")
                        return 1
                return 0
            except:
                print(result.stdout)
                print("Error in checking if the VM already exists, exiting.")
                return 1
    return 1


# count Windows password necessary specifications satisfied (3 of lowercase, uppercase, numbers and special characters)
def pwd_check_regex(admin_password):
    lowercase = r'[a-z]'
    uppercase = r'[A-Z]'
    special_chars = r'[!@#$%^&*(),.?":{}|<>]'
    numbers = r'\d'

    num_lowercase = len(re.findall(lowercase, admin_password))
    num_uppercase = len(re.findall(uppercase, admin_password))
    num_special = len(re.findall(special_chars, admin_password))
    num_numbers = len(re.findall(numbers, admin_password))

    conditions_met = 0
    if (num_lowercase >= 1):
        conditions_met += 1
    if (num_uppercase >= 1):
        conditions_met += 1
    if (num_special >= 1):
        conditions_met += 1
    if (num_numbers >= 1):
        conditions_met += 1
    
    return conditions_met


# get GCP config file details to create a VM and log file from them
def get_gcp_fields():
    config = configparser.ConfigParser()
    config.read("gcp.conf")
    num = 1
    read = False

    # get datetime and set up output txt file
    datestamp = str(datetime.now())
    datestamp = (datestamp.split("."))[0]
    datestamp = datestamp.replace(" ", ":")

    filename = "VMcreationGCP_" + datestamp + ".txt"
    file = open(filename, 'a')
    file.write("Date Stamp: " + datestamp + "\n")
    # get from shell metadata as per professor Yan
    user = subprocess.run('whoami', universal_newlines=True, capture_output=True)
    user = user.stdout
    file.write("System Admin Name: " + user + "\n")

    while num != 10:
        vm = "gcp" + (str(num)).zfill(2)
        try:
            # get list of fields in the config file
            fields = []
            for key,value in config.items(vm):
                fields.append(key)

            name = config[vm]['name']
            image = config[vm]['image']
            # required for my purposes, but not needed in creation
            if "os" in fields:
                ops = config[vm]['os']
            else:
                if (("Win" in image) or ("win" in image)):
                    ops = "windows"
                else:
                    ops = "linux"
            location = config[vm]['zone']
            machine = config[vm]['machine-type']
            imageproject = config[vm]['imageproject']
            if "open-ports" in fields:
                port = config[vm]['open-ports']
            else:
                port = "443"
            if "port-priority" in fields:
                port_priority = config[vm]['port-priority']
            else:
                port_priority = 100

            num += 1
            read = True
            type = "GCP"

            # check if the port and port priority number is appropriate
            if int(port_priority) < 100 or int(port_priority) > 4096:
                print("Error: Port priority number must be between 100 and 4096. Exiting this VM's creation.")
                return False
            ports = port.split(",")
            for item in ports:
                if int(item) != 443 and int(item) != 80:
                    print(3)
                    print("Error: Only ports 443 or 80 are accepted.")
                    return False

            success = create_GCP_VM(fields, name, image, location, machine, imageproject, port, port_priority)

            if success == 0:
                # get GCP VM status and print to txt file
                time.sleep(2)
                try:
                    print("Command (get VM status): gcloud compute instances describe", name, "--zone", location, "--format json")
                    result = subprocess.run(['gcloud','compute','instances','describe',name,'--zone',location,'--format','json'],\
                                            universal_newlines = True, capture_output = True)
                    output = result.stdout
                    print(output)
                    data = json.loads(output)
                    powerState = data['status'].title()
                    
                    # output VM details to file (for each vm) v problem!!
                    write_txt(fields, type, file, config, vm, name, ops, image, location, powerState)
                except:
                    print(result.stderr)
                    return 1
        except:
            break
    
    file.close()
    return read


# create gcp VM from config fields
def create_GCP_VM(fields, name, image, location, machine, imageproject, port, port_priority):
    cmd_machine = '--machine-type=' + machine
    cmd_zone = '--zone=' + location
    cmd_image = '--image=' + image
    cmd_imageproject = '--image-project=' + imageproject
    
    print("\nName:", name)
    args = ['gcloud','compute','instances','create',name,\
            cmd_machine,\
            cmd_zone,\
            cmd_image,\
            cmd_imageproject,\
            '--subnet=default',\
            '--async']
    command = ""
    for arg in args:
        command = command + arg + " "
        
    print("Command: " + command + "\nAre you okay with executing the creation of this VM? y/n")
    response = input()
    if response == "y":
        # check if the image exists, no deprecated images allowed as per Yan
        filter = "--filter=name:" + (image.split("-"))[0]
        command2 = "gcloud compute images list " + filter + " --format json"
        print("Command (check if image exists):", command2)
        result = subprocess.run(['gcloud','compute','images','list',filter,'--format','json'],\
                                universal_newlines=True, capture_output=True)
        output = result.stdout
        print(output)
        data = json.loads(output)
        images = [item['name'] for item in data]
        if image not in images:
            print(result.stdout)
            print("Error: Image", image, "does not exist in zone", location, "so exiting this VM.")
            print(1)
            return 1
        
        try:
            # check if the VM already exists, don't create it if so
            print("Command (check if VM already exists): gcloud compute instances describe", name, "--zone", location, "--format json")
            result = subprocess.run(['gcloud','compute','instances','describe',name,'--zone',location,'--format','json'],\
                                    universal_newlines = True, capture_output = True)
            output = result.stdout
            print(output)
            data = json.loads(output)
            # vm exists
            if len(data) != 0:
                print("VM already exists.")
                return 1
            # just in case, will likely just hit the except
            else:
                print("VM does not yet exist!")
                print("Command (create VM):", command)
                result = subprocess.run(args)
                if result.returncode != 0:
                    return 1
                
                # created the vm successfully
                else: 
                    # port dealings if specified in config file
                    if "open-ports" in fields:
                        # sleep before opening port to allow vm time to create
                        print("Allowing the VM 10 seconds to create before opening the port.")
                        time.sleep(10)

                        if int(port_priority) < 100 or int(port_priority) > 4096:
                            print("Error: Port priority number must be between 100 and 4096. Exiting this VM's creation.")
                            return 1
                        ports = port.split(",")
                        for item in ports:
                            if int(item) != 443 and int(item) != 80:
                                print("Error: Only ports 443 or 80 are accepted.")
                                return 1
                            
                        # open designated ports from .conf and assign priority
                        print("\nOpening .conf designated ports, please stand by.")
                        try:
                            zone = "--zone=" + location
                            if port == "80":
                                print("Command (open port): gcloud compute instances add-tags", name, zone, "--tags http-server")
                                result = subprocess.run(['gcloud','compute','instances','add-tags',name, zone, '--tags', 'http-server']) 
                            elif port == "443":
                                print("Command (open port): gcloud compute instances add-tags", name, zone, "--tags https-server")
                                result = subprocess.run(['gcloud','compute','instances','add-tags',name, zone, '--tags', 'https-server'])
                            else:
                                print("Command (open port): gcloud compute instances add-tags", name, zone, "--tags http-server,https-server")
                                result = subprocess.run(['gcloud','compute','instances','add-tags',name, zone, '--tags', 'http-server,https-server'])
                            
                            if result.returncode != 0:
                                return 1
                            else:
                                # prints output automatically because not piped
                                return 0
                        except:
                            print("Error: Open port", port, "failed to run.")
                            return 1
                    return 0

        # VM data can't be fetched, vm doesn't exist so create it      
        except:
            print(output)
            print("Command (create VM):", command)
            result = subprocess.run(args)
            if result.returncode != 0:
                return 1

            # created VM successfully
            else:
                # port dealings if specified in config file
                if "open-ports" in fields:
                    # sleep before opening port to allow vm time to create
                    print("Allowing the VM 10 seconds to create before opening the port.")
                    time.sleep(10)

                    if int(port_priority) < 100 or int(port_priority) > 4096:
                        print("Error: Port priority number must be between 100 and 4096. Exiting this VM's creation.")
                        return 1
                    ports = port.split(",")
                    for item in ports:
                        if int(item) != 443 and int(item) != 80:
                            print("Error: Only ports 443 or 80 are accepted.")
                            return 1
                        
                    # open designated ports from .conf and assign priority, commented out for brevity
                    print("\nOpening .conf designated ports, please stand by.")
                    try:
                        zone = "--zone=" + location
                        if port == "80":    
                            print("Command (open port): gcloud compute instances add-tags", name, zone, "--tags http-server")
                            result = subprocess.run(['gcloud','compute','instances','add-tags',name,zone, '--tags', 'http-server'])
                        elif port == "443":
                            print("Command (open port): gcloud compute instances add-tags", name, zone, "--tags https-server")
                            result = subprocess.run(['gcloud','compute','instances','add-tags',name,zone, '--tags', 'https-server'])
                        else:
                            print("Command (open port): gcloud compute instances add-tags", name, zone, "--tags http-server,https-server")
                            result = subprocess.run(['gcloud','compute','instances','add-tags',name,zone,'--tags', 'http-server,https-server'])
                        if result.returncode != 0:
                            return 1
                        else:
                            # prints output automatically because not piped
                            return 0
                    except:
                        print("Error: Open port", port, "failed to run.")
                        return 1
                return 0 
    return 0


# write log text file per OS details
def write_txt(fields, type, file, config, vm, name, ops, image, location, powerState):
    file.write("Name: " + name + "\n")
    if "project" in fields:
        file.write("Project: " + config[vm]['project'] + "\n")
    else:
        file.write("Project: default\n")
    if "purpose" in fields:
        file.write("Purpose: " + config[vm]['purpose'] + "\n")
    else:
       file.write("Purpose: default\n") 
    if "team" in fields:
        file.write("Team: " + config[vm]['team'] + "\n")
    else:
        file.write("Team: default\n")
    if "os" in fields:
        file.write("OS: " + ops + "\n")
    else:
        file.write("OS: linux (default)\n")

    # extra information up to status (not required)
    file.write("Image: " + image + "\n")
    if "admin-username" in fields:
        file.write("Admin User: " + config[vm]['admin-username'] + "\n")

    # Azure exclusives
    if (type == "Azure"):
        file.write("Location: " + location + "\n")
        file.write("Resource Group: " + config[vm]['resource-group'] + "\n")
        file.write("Priority: " + config[vm]['priority'] + "\n")
        file.write("Authentication Type: " + config[vm]['authentication-type'] + "\n")
    
    # GCP exclusives
    if (type == "GCP"):
        file.write("Zone: " + location + "\n")
        file.write("Image Project: " + config[vm]['imageproject'] + "\n")
        file.write("Machine Type: " + config[vm]['machine-type'] + "\n")

    if "open-ports" in fields:    
        file.write("Open Ports: " + config[vm]['open-ports'] + "\n")
    if "port-priority" in fields:
        file.write("Port Priority: " + config[vm]['port-priority'] + "\n")
    file.write("Status: " + powerState.strip() + "\n\n")
