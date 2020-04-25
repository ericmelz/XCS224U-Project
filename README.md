# XCS224U-Project
Final Project for XCS224U - Natural Language Understanding

## Setup

### AWS EC2 Specs
Ubuntu Server 18.04 LTS (HVM), SSD Volume Type - ami-0f56279347d2fa43e  (64-bit x86)
m5.2xlarge (8 vCPUs, 32G RAM)
public subnet
Enable auto-assign Public IP
64G storage
Tags: Name=nlu
Security Group: Create new, add inbound rule: Custom TCP, Port 8888, Source 0.0.0.0/0  Description: Jupyter

### Local ~/.ssh/config
```
Host nlu
  HostName 13.56.249.132  # substitute IP here
  User ubuntu
  IdentityFile ~/keys/nlu.pem
```

### Login
```
ssh nlu
```

### Setup Commands




