setcmd(){

mac=`cat summary.log | grep "LAN" | grep "Mac" | awk -F: '{print $3}' | awk 'NR == 1 {print $1}'`
mac_txt=`echo ${mac} | sed 's/../&-/g; s/-$//'`

wget 172.21.57.147/script/fetch_ins.sh
chmod 777 fetch_ins.sh
./fetch_ins.sh

source ins-${mac_txt}

command="cburn-$2%20NOINS%20QMCAUTH%20DIR=$1"


#ipxe
url="http://172.21.0.1/cgi-bin/autoipxe.php?command=${command}+$2&address=${mac}+&action=Update"
echo ${url}
re=$(curl -s "$url")
if [[ ${re} == *"${mac} => OK"*  ]];
then
echo -e "\033[1;32mSetting up ipxe cburn log command success...\033[0m" > /dev/tty1
else 
echo -e "\033[1;32mSetting up ipxe cburn log command failed...\033[0m" > /dev/tty1
exit
fi


#pxe
url1="http://172.21.0.1/cgi-bin/autopxe.php?command=${command}+$2&address=${mac}+&action=Update"

re=$(curl -s "$url1")
if [[ ${re} == *"${mac} => OK"*  ]];
then
echo -e "\033[1;32mSetting up pxe cburn log command success...\033[0m" > /dev/tty1
else 
echo -e "\033[1;32mSetting up pxe cburn log command failed...\033[0m" > /dev/tty1
exit
fi

}

