#!/bin/bash
VER=1.0.0-6.dev
BNAME="azure-autoscaling"
# clean up
rm -fr $BNAME.$VER.zip $BNAME-$VER.md5sum.txt

md5sum * > $BNAME-$VER.md5sum.txt
zip -r $BNAME.$VER.zip *
md5sum $BNAME.$VER.zip >> $BNAME-$VER.md5sum.txt

