wget 172.21.57.147/script/install_mst.sh
chmod 777 install_mst.sh
./install_mst.sh

mst start
aoc_list=`mst status | grep "/dev/mst/" | awk -F'-' '{print $1}'`

for aoc in ${aoc_list}
do
echo -e "\033[1;32mTry to update FW for ${aoc} ...\033[0m" > /dev/tty1
echo y | flint -d ${aoc} -i $1 burn | tee -a ~/update_process.log > /dev/tty1

done
mlxfwmanager | tee -a ~/update_process.log > /dev/tty1
ipmicfg -raw 0x30 0xd









