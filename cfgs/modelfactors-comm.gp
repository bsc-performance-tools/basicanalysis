
#Gnuplot template for the projection functions

#Prepare the axes
#REPLACE_BY_XRANGE
set xlabel "Number of Processes"
set logscale x
set yrange [0:110]
set ylabel "Efficiency"
set ytics ( 0, "10%%" 10, "20%%" 20, "30%%" 30, "40%%" 40, "50%%" 50, "60%%" 60, "70%%" 70, "80%%" 80, "90%%" 90, "100%%" 100 )
set grid ytics

set style line 1 lt 7 dt 2 lw 1.5 lc rgb "red"
set style line 2 lt 7 dt 2 lw 1.5 lc rgb "green"
set style line 3 lt 7 dt 2 lw 1.5 lc rgb "orange"
set style line 4 lt 7 dt 2 lw 1.5 lc rgb "blue"
set style line 5 lt 7 dt 2 lw 1.5 lc rgb "magenta"

set key left bottom Left reverse


plot '-' with linespoints title "Communication Efficiency" ls 1,\
     '-' with linespoints title "Serialization Efficiency" ls 2,\
     '-' with linespoints title "Transfer Efficiency" ls 3

