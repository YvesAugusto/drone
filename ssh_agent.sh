#!/bin/sh
eval $(ssh-agent)
ssh-add /home/pi/.ssh/drone_deploy_key