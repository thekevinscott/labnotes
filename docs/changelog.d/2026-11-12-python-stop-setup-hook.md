Stopping an experiment during setup now sends the setup hook SIGTERM, then kills it on a second stop, instead of waiting for it to finish. Teardown runs once setup has exited.
