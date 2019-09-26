# TestStand Executor

This is an example on how to leverage SystemLink to remotely execute TestStand sequences, however it could be modified to execute other applications.  It leverages the SystemLink System Management job execution engine built on Salt to run and queue tests as well as the SystemLink TestStand reporting plugin to monitor the current or most recent test results.  All test results are logged to the SystemLink Test Monitor application.

__Initial Server Setup__
* Install the SystemLink Server
* Install the SystemLink Test Module

__Initial Client Setup__

* Install TestStand and LabVIEW 2019 64-bit (may work with other versions or just the runtime)
* Install the SystemLink Client
* Add the client to a SystemLink Server
* See the [SystemLink YouTube channel](https://www.youtube.com/channel/UCJFhOcqtxl-5kDb-tclTggQ) for more information

__Running this Example__

* Install ni-teststandexecutor_1.0.0.7_windows_x64.nipkg on the client
* Install ni-computermotherboardtest_2.0.0.0_windows_x64.nipkg on the client
* Reboot the client
* Copy /plugins/test-executor folder to C:\Program Files\National Instruments\Shared\Web Server\htdocs\plugins\test-executor\ on the SystemLink Server
* Copy /conf folder to C:\Users\jprewitt\Documents\GitHub\teststand-executor\conf\ on the SystemLink Server
* Use the NI Web Server Configuration utility to restart the web server

__Updating the WebVI__

You will at a minimum need to update the WebVI drop down of systems to match your test systems hostnames.
* When running the WebVI in NXG you will need to use the NI Web Server Configuration utility to enable CORS
* In the WebVI set the server, username and password to match the credentials for your server
* Update the drop down of systems to match your test systems hostnames
* Once you have verified the TestExecutor WebVI works you need to build the WebApp.gcomp
* Go to the build output and copy the contents to C:\Program Files\National Instruments\Shared\Web Server\htdocs\plugins\test-executor\
* Use the NI Web Server Configuration utility to restart the web server
* After restarting the web server you may have to clear your browser cache

__TODO__
* Figure out how to dynamically populate the dropdown based in systems with the TestStand Executor installed
* Add an option to automatically pick a tester based on whether or not it supports the test, is online, and queue size
