
#Gnuplot template for the projection functions

#REPLACE_BY_TRACE_NAMES
#REPLACE_BY_XRANGE
set xlabel "Number of Processes"
#REPLACE_BY_XTICS_LABEL
## set logscale x
#REPLACE_BY_YRANGE
set ylabel "Efficiency (%)"
# set ytics ( 0, "10%%" 10, "20%%" 20, "30%%" 30, "40%%" 40, "50%%" 50, "60%%" 60, "70%%" 70, "80%%" 80, "90%%" 90, "100%%" 100 )
# set grid ytics

set style line 1 lt 5 dt 2 lw 1.5 lc rgb '#1c1044' # dark blue

set style line 2 lt 8 dt 2 lw 1.5 lc rgb "forest-green"
set style line 3 lt 6 dt 2 lw 1.5 lc rgb '#00FF00' # lime
set style line 4 lt 5 dt 2 lw 1.5 lc rgb '#008B8B' # darkcyan


set style line 8 lt 4 dt 2 lw 1.5 lc rgb '#7CFC00' # lawngreen
set style line 9 lt 4 dt 2 lw 1.5 lc rgb '#00FFFF' # cyan


set key left bottom Left reverse


plot '-' with linespoints title "MPI Parallel efficiency" ls 2,\
     '-' with linespoints title "MPI Load balance" ls 3,\
     '-' with linespoints title "MPI Communication efficiency" ls 4,\
     '-' with linespoints title "Serialization Efficiency" ls 8,\
     '-' with linespoints title "Transfer Efficiency" ls 9
