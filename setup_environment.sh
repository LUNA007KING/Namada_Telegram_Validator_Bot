#!/bin/bash

read -sp 'Enter the MySQL root password: ' root_password
echo

echo "Do you want to set a new user different from root? (y/n)"
read -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    read -p 'Enter the new MySQL user name [default: root]: ' new_user
    read -sp 'Enter the password for the new user [default: same as root password]: ' new_user_password
    echo
    if [ -z "$new_user" ]
    then
        new_user="root"
    fi
    if [ -z "$new_user_password" ]
    then
        new_user_password="$root_password"
    fi
else
    new_user="root"
    new_user_password="$root_password"
fi

sudo apt-get update
sudo apt-get install python3 python python3-venv python3-pip -y
sudo apt-get install -y mysql-server

sudo mysql_secure_installation <<EOF

Y # Setup VALIDATE PASSWORD plugin
0 # Password validation policy (0=LOW, 1=MEDIUM, 2=STRONG)
$root_password # Set your root password
$root_password # Confirm your root password
Y # Remove anonymous users
Y # Disallow root login remotely
Y # Remove test database and access to it
Y # Reload privilege tables
EOF

sudo mysql -u root -p"$root_password" <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$root_password';
FLUSH PRIVILEGES;
EOF

if [ "$new_user" != "root" ]; then
    sudo mysql -u root -p"$root_password" <<EOF
CREATE USER '$new_user'@'localhost' IDENTIFIED BY '$new_user_password';
GRANT ALL PRIVILEGES ON *.* TO '$new_user'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOF
fi

echo "MySQL installation and basic configuration are completed!"
