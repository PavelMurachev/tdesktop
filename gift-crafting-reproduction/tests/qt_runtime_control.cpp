#include <QtWidgets/QApplication>
#include <iostream>

// A negative-control application containing no Telegram code or gift adapters.
int main(int argc, char **argv) {
    QApplication application(argc, argv);
    std::cout << "Qt runtime: " << qVersion() << std::endl;
    std::cout << "CONTROL: QApplication created; returning through its destructor" << std::endl;
    return 0;
}
