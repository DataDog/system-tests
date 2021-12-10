.NET
* Andrew Lock
* Robert Pickering
* Tony Redondo
* Kevin Gosse
* Anna Yafi
* Pierre Bonnet
* Lucas Pimentel
* Zach Montoya

Ruby

Go
* Felix Geisendorfer

NodeJS
* Bryan English
* Juan Fernandez


## TOC

### Self presentation

### What are issue we want to tackle ? 

* Unit test are "unit"
  * Lot of issue comes for interaction between several components
  * And even, for complex components, utnit tests tends to validate each component part separately, but misses some issues caused by interactions between all components's part
* Usually, developers tends to to "high-level" unit testing, aka spawns the component entirely, and do functionnal testing
  * slow due to the test-isolation golden law in unit testing
  * painfull
  * context of 7 langs doing the same thing


### The solution

* Workbench that spawns Lib (aka tracers), agent, and a backend, put spies everywhere, send a signal (HTTP request), and validate that everything accessible is OK

### System test key principle

* Functional testing (but it can do more)
* Black box testing
* No test isolation ()

### System test pain points

* Can be hard to understand the root cause of issues
* requires a strong effort to avoid flakyness (on test side, but also on component side)

### System tests good points

* Reasonably fast
* High probality of catching functional bugs

### What a test looks like

* Python
* Decorators
* flag tests

### Dashboard

* 
*
*

### QA Agenda

