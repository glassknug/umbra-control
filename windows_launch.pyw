"""Source launcher; packaged builds use windows_app.py."""
from windows_launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
