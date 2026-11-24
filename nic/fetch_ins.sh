mac=`cat summary.log | grep "LAN" | grep "Mac" | awk -F: '{print $3}' | awk 'NR == 1 {print $1}'`
mac=`echo ${mac} | sed 's/../&-/g; s/-$//'`

wget http://172.21.0.1/instructions/ins-${mac}

cp ins-${mac} ins-${mac}.py

source ins-${mac}

