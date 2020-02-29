#!/bin/gnuplot 
set output "./efficiency_table.png"
set terminal pngcairo enhanced dashed crop size 1100,390 font "Latin Modern Roman,18"

set datafile separator ","

set title ""
unset key

set format cb "%.0f%%"
set cbrange[0:100]
set tmargin 1
#set cbtics offset 0,0 
#set colorbox horizontal
#set colorbox user origin 0.3,0.3 size 0.6,0.05


set cbtics ('<80%%' 80, "85%%" 85, "90%%" 90, "95%%" 95, "100%%" 100)
# # Color palette
# # Google Spreadsheet palette
set palette defined (0.00 "#E67C73", 0.50 "#E1D666", 1.00 "#57BB8A")
# # Paraver palette
# #set palette defined (0.00 "#00ff00", 0.80 "#00ff00", 0.90 "#007777", 1.00 "#0000ff")


set xtics offset 0,9.8
set ytics offset -25,0 left
set yrange [] reverse

plot \
  'efficiency_table.csv' \
    matrix rowheaders columnheaders using 1:2:3 with image, \
  'efficiency_table.csv' \
    matrix rowheaders columnheaders using 1:2:(sprintf("%.2f",$3) ) with labels
