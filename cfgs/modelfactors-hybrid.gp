
#Gnuplot template for the projection functions

#REPLACE_BY_TRACE_NAMES
#REPLACE_BY_XRANGE
set xlabel "Number of Processes"
#REPLACE_BY_XTICS_LABEL
## set logscale x
set yrange [0:110]
set ylabel "Efficiency"
set ytics ( 0, "10%%" 10, "20%%" 20, "30%%" 30, "40%%" 40, "50%%" 50, "60%%" 60, "70%%" 70, "80%%" 80, "90%%" 90, "100%%" 100 )
set grid ytics


set style line 1 lt 8 dt 2 lw 2.0 lc rgb '#4B0082' # indigo

set style line 2 lt 7 dt 2 lw 1.5 lc rgb "forest-green"
set style line 3 lt 6 dt 2 lw 1.5 lc rgb '#00FF00' # lime
set style line 4 lt 6 dt 2 lw 1.5 lc rgb '#008B8B' # darkcyan

set style line 5 lt 5 dt 2 lw 1.5 lc rgb "red"
set style line 6 lt 4 dt 2 lw 1.5 lc rgb "orange"
set style line 7 lt 4 dt 2 lw 1.5 lc rgb "salmon"

set key left bottom Left reverse



plot '-' with linespoints title "Hybrid Efficiency" ls 1,\
     '-' with linespoints title "MPI Parallel efficiency" ls 2,\
     '-' with linespoints title "MPI Load balance" ls 3,\
     '-' with linespoints title "MPI Communication efficiency" ls 4,\
#REPLACE_BY_OMP_PAR_EFF
#REPLACE_BY_OMP_LB
#REPLACE_BY_OMP_COMM


