#!/bin/bash

cd /home/khaki/item/neteasySpider
ret=`ps aux | grep "python neteasy.py" | wc -l`

if [ "$ret" != "2" ];then
    python sendmail.py
fi