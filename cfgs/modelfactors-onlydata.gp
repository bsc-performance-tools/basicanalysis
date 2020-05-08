
#Gnuplot template for the projection functions

#REPLACE_BY_TRACE_NAMES
#REPLACE_BY_XRANGE
set xlabel "Number of Processes"
#REPLACE_BY_XTICS_LABEL
# set logscale x
#REPLACE_BY_YRANGE
## set yrange [0:]
set ylabel "Efficiency (%)"

# set ytics ( 0, "10%%" 10, "20%%" 20, "30%%" 30, "40%%" 40, "50%%" 50, "60%%" 60, "70%%" 70, "80%%" 80, "90%%" 90, "100%%" 100 )
# set grid ytics

set style line 1 lt 8 dt 2 lw 2.0 lc rgb '#4B0082' # indigo
set style line 2 lt 7 dt 2 lw 1.5 lc rgb "red"
set style line 3 lt 7 dt 2 lw 1.5 lc rgb "green"

set style line 4 lt 5 dt 5 lw 1.5 lc rgb "blue"
set style line 5 lt 3 dt 1 lw 1.8 lc rgb "dark-grey"

set key left bottom Left reverse


plot '-' with linespoints title "Parallel Efficiency" ls 1,\
     '-' with linespoints title "Load Balance" ls 2,\
     '-' with linespoints title "Communication Efficiency" ls 3,\
     '-' with linespoints title "Computation Scalability" ls 4,\
     '-' with linespoints title "Global Efficiency" ls 5

