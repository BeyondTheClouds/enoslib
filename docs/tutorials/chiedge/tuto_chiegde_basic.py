import logging
import os
import enoslib as en

en.init_logging(level=logging.INFO)

prefix = os.getlogin()

provider_conf = {
    "lease_name": f"{prefix}-enoslib-chiedge-lease",
    "rc_file": "./my-app-cred-edge-openrc.sh",  # FIXME use your OPENRC file
    "walltime": "01:00:00",
    "resources": {
        "machines": [
            {
                "roles": ["server", "cloud"],
                "machine_name": "jetson-nano",
                "count": 2,
                "container": {
                    "name": f"{prefix}-server-container",
                    "image": "ubuntu",
                    # additional arguments
                    "command": ["/bin/bash"],
                    "hostname": "my-jetson-nano",
                    "environment": {"a": "1", "b": "2"},
                },
            },
            {
                "roles": ["client", "edge", "iot"],
                "device_name": "iot-jetson06",
                "container": {
                    "name": "cli-container",
                    "image": "ubuntu",
                },
            },
        ],
    },
}

conf = en.ChameleonEdgeConf.from_dictionnary(provider_conf)
provider = en.ChameleonEdge(conf)

try:
    # get testbed resources
    roles, networks = provider.init()
    print("*" * 40 + f"roles{type(roles)} = {roles}")
    print("*" * 40 + f"networks{type(networks)} = {networks}")
    for role, devices in roles.items():
        for device in devices:
            print("*" * 20 + f" role[{role}] / device[{device.uuid}]")

    # experiment logic
    # Running commands on devices (commands, upload, and download)
    # For CHI@Edge devices, instead of using "run_command"
    result = en.run_command(command="ls -la /tmp/", roles=roles)
    # You should use: "execute", "upload", or "download"
    for device in roles["server"]:
        print("*" * 60 + f" Running command inside a running container: ls -la /tmp/")
        dir_content = device.execute("ls -la /tmp/")
        print(f"Directory content = {dir_content['output']}")

        print("*" * 60 + f" Uploading files to a running container")
        cmd_upload = device.upload("./files-to-upload/", "/tmp")
        print(f"cmd_upload={cmd_upload}")

        print("*" * 60 + f" Running command inside a running container: ls -la /tmp/")
        dir_content = device.execute("ls -la /tmp/")
        print(f"Directory content = {dir_content['output']}")

        print("*" * 60 + f" Downloading files from a running container")
        print("Download files")
        device.download("/tmp", "./downloaded-files/")

        print("Getting container logs")
        container_logs = device.get_logs()
        print(f"container logs: {container_logs if container_logs else 'No logs.'}")

        # print("Getting public IP")
        # print(f"container public IP: {device.associate_floating_ip()}")
except Exception as e:
    print(e)
finally:
    # provider.destroy()
    pass
