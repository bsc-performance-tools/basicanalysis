BasicAnalysis User Guide
========================

**BasicAnalysis** automates the extraction of POP performance metrics from Paraver 
traces. These metrics help diagnose how efficiently a parallel application is 
running with respect to performance factors such as load balance, communication, 
and computation scalability, and help identify factors that may limit application 
scalability.

The tools extracts the performance data required to compute the 
efficiency metrics and organizes the results into complementary analytical views. 
The generated reports expose the relationships between the metrics and provide 
interpretation guidance, possible causes of efficiency losses, and possible next 
steps for further performance analysis.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   01_introduction
   02_getting_started
   03_running_basicanalysis
   04_staged_workflow
   05_methodology
   06_metrics
   07_performance_report
   08_output
   09_limitations