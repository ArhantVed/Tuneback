"""
Tuneback — entry point.

Run this file to launch the application:
    python main.py
"""

from ui.app import App


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
