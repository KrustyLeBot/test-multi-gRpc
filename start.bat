start pythonw server.py

for /L %%A in (1,1,2) do (
    REM start pythonw client.py False
    start pythonw client.py True
)