
#Gnuplot template for the projection functions

#REPLACE_BY_TRACE_NAMES
#REPLACE_BY_XRANGE
#REPLACE_BY_XLABEL
#REPLACE_BY_XTICS_LABEL
# set logscale x
#REPLACE_BY_YRANGE
set ylabel "Efficiency (%)"
# set ytics ( 0, "10%%" 10, "20%%" 20, "30%%" 30, "40%%" 40, "50%%" 50, "60%%" 60, "70%%" 70, "80%%" 80, "90%%" 90, "100%%" 100 )
# set grid ytics

set style line 1 lt 5 dt 2 lw 2.0 lc rgb "blue"
set style line 2 lt 7 dt 2 lw 1.5 lc rgb "cyan"
# set style line 2 lt 7 dt 2 lw 1.5 lc rgb '#6A5ACD' # slateblue
set style line 3 lt 7 dt 2 lw 1.5 lc rgb '#4682B4' # steelblue
set style line 4 lt 7 dt 2 lw 1.5 lc rgb '#8A2BE2' # blueviolet

set key left bottom Left reverse


#REPLACE_BY_SCALE_PLOT

