#!/bin/bash

# ECO #34097: Update Mellonox Connect X-7 AOC-755106AS_HEAT

# 2026/6/4 v1.0 B5 SI Team

FLINT="mstflint"
CONFIG="mstconfig"

FW_FILE=fw-ConnectX7-rel-28_47_2682-MCX755106AS-HEA_Ax-UEFI-14.40.10-FlexBoot-3.8.201.signed.bin

# turn off overheat LED
function overheat_OFF() {
	ipmitool raw 0x30 0x70 0x65 00
}

# turn on overheat LED
function overheat_ON() {
	ipmitool raw 0x30 0x70 0x65 01
}

# turn off UID LED
function UID_OFF() {
	ipmitool raw 0x30 0xe
}

# turn on UID LED
function UID_ON() {
	ipmitool raw 0x30 0xd
}

# load cburn functions
. /usr/local/bin/functions

# load stage1.conf as variables
. /root/stage1.conf

outputct "${_YEL}URC${_DEF}: Initializing script\n"
sync

# clear LED indicators
# turn off overheat LED
overheat_OFF
# turn off UID LED
UID_OFF

# get INSDIR if given at PXE
if [[ $INSDIR =~ [a-z0-9]+ ]]; then
	ORD=$INSDIR
	LOGFILE="/mnt/$ORD/${LNK_MAC//:/-}/draft29019.log"
fi

# get order number from instruction file
if [[ ! $ORD =~ [a-z0-9]+ ]]; then
# get INS file with stage1 LNK_MAC variable
	wget -N -T 15 -q -P /root http://cburnserver/instructions/ins-${LNK_MAC//:/-} || (outputct "${_YEL}URC${_DEF}: ${_RED}Can not find instruction file ...${_DEF}\n")
	if [ -e ins-${LNK_MAC//:/-} ]; then
		ORD=`grep -E "^ORDNUM" ins-${LNK_MAC//:/-} | awk -F '["'\''/]' '{print tolower($2)}'`
		if [[ ! $ORD =~ [a-z0-9]+ ]]; then
			ORD=`grep -E "^DIR" ins-${LNK_MAC//:/-} | awk -F '["'\''/]' '{print tolower($2)}'`
		fi
	fi
# set directory to save log to
	if [[ $ORD =~ [a-z0-9]+ ]]; then
		YEAR=`date +%Y`
		if [ -d "/mnt/$YEAR" ] && [ -d "/mnt/$YEAR/$ORD" ]; then
			FOLDER="/mnt/$YEAR/$ORD/draft29019"
		else
			FOLDER="/mnt/$ORD/draft29019"
		fi
	else
	# default directory if ORD is not set
		FOLDER="/mnt/draft29019"
	fi
	if [ ! -d $FOLDER ]; then
		mkdir -p $FOLDER
	fi
# set log file variable
	LOGFILE="$FOLDER/${LNK_MAC//:/-}.txt"
fi

# move existing log
if [ -e $LOGFILE ]; then
# generate timestamp
	DATE=`stat -c %z $LOGFILE | awk '{print $1}' | tr -d '-'`
	mv $LOGFILE $LOGFILE.$DATE
fi
> $LOGFILE

# install latest version of mellanox utility
if [ "$(which $FLINT 2> /dev/null)" == "" ] || [[ $($FLINT -v) =~ 4\.12 ]]; then
	wget http://172.21.100.1/RC/package/mft-4.18.0-106.x86_64.rpm
	rpm -Uvh mft-4.18.0-106.x86_64.rpm > /dev/null 2>&1
	FLINT="flint"
	CONFIG="mlxconfig"
fi
# get firmware file from production RC server
	wget http://172.21.100.1/RC/package/$FW_FILE

if [[ ! -e "$FW_FILE" ]]; then
	outputct "${_YEL}URC${_DEF}: ${_RED}Failed to retrieve firmware file${_DEF}\n";
	# turn on overheat LED
	overheat_ON
	sleep inf
fi

# get PCI ID of Mellanox cards
	PCI=()
	for ID in $(lspci -d 15b3: | awk '{print $1}' | grep -E '\.0$'); do
		PSID=`$FLINT -d $ID q | grep "PSID:" | awk '{print $NF}'`
		if [[ $PSID =~ MT_0000000834 ]]; then
			PCI+=($ID)
		fi
	done
	if (( ${#PCI[@]} < 1 )); then
		#switch flint tool if other does not work
		if [[ $FLINT =~ "mst" ]]; then
			FLINT="flint"
		else
			FLINT="mstflint"
		fi
		PCI=()
		for ID in $(lspci -d 15b3: | awk '{print $1}' | grep -E '\.0$'); do
			PSID=`$FLINT -d $ID q | grep "PSID:" | awk '{print $NF}'`
			if [[ $PSID =~ MT_0000000834 ]]; then
				PCI+=($ID)
			fi
		done
	fi
	if (( ${#PCI[@]} < 1 )); then
		outputct "${_YEL}URC${_DEF}: ${_RED}No compatible Mellanox card detected, aborting.${_DEF}\n";
		# turn on overheat LED
		overheat_ON
		sleep inf
	fi

# check card PSID info
	for PCI_ID in ${PCI[@]}; do
		PSID=`$FLINT -d $PCI_ID q | grep "PSID:" | awk '{print $NF}'`
		if [[ ! $PSID =~ MT_0000000834 ]]; then
			outputct "${_YEL}URC${_DEF}: ${_RED} Card in $PCI_ID is not compatible, aborting.${_DEF}\n";
			# turn on overheat LED
			overheat_ON
			sleep inf
		fi
	done

	outputct "${_YEL}URC${_DEF}: Starting draft 29019 Mellanox AOC update\n"

# update card FW
	for PCI_ID in ${PCI[@]}; do
		PSID=`$FLINT -d $PCI_ID q | grep "PSID:" | awk '{print $NF}'`
		if [ "$PSID" == "MT_0000000834" ]; then
			$FLINT -d $PCI_ID -y -i $FW_FILE b &
		fi
	done
# wait until cards finish updating
	while (( $(ps -ef | grep $FLINT | grep -cv grep) > 0 )); do
		sleep 5
	done

# print FW and settings
	for PCI_ID in ${PCI[@]}; do
		$FLINT -d $PCI_ID q >> $LOGFILE
		$CONFIG -d $PCI_ID -e q >> $LOGFILE
	done

	outct "${_GRN}draft 29019 Mellanox AOC update completed${_DEF}\n"
	outputct "${_YEL}URC${_DEF}: Power cycle the system for the update to take effect\n"
	# turn on UID LED
	UID_ON
	sleep inf
