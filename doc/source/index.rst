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

   introduction
   getting_started
   running_basicanalysis
   staged_workflow
   methodology
   metrics
   performance_report
   output
   limitations