#!/bin/gnuplot 
set output "./efficiency_table.png"

#Prepare the plot size

#REPLACE_BY_SIZE

set datafile separator ","

set title ""
unset key

set format cb "%.0f%%"
set cbrange[0:100]
set tmargin 1


set cbtics ('<50%%' 50, '60%%' 60, '70%%' 70, '80%%' 80, "90%%" 90, "100%%" 100)

set palette defined (0.00 "#000000", 0.01 "#FF0000", 0.60 "#E67C73", 0.75 "#F9950A", 0.85 "#AADC32", 0.90 "#5CC863", 1.00 "#57BB8A")  


set xtics offset 0,15
set ytics offset -27,0 left
set yrange [] reverse

plot \
  'efficiency_table.csv' \
    matrix rowheaders columnheaders using 1:2:3 with image, \
  'efficiency_table.csv' \
    matrix rowheaders columnheaders using 1:2:(sprintf("%.2f",$3) ) with labels
