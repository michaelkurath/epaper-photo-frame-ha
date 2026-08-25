#include <cassert>
#include <cstdint>
#include <iostream>

#include "../ee02_photo_frame/firmware_core.h"

int main() {
  using namespace photo_frame;

  static_assert(validGeometry(1200, 1600, kP133PortraitWidth,
                              kP133PortraitHeight));
  static_assert(validGeometry(1600, 1200, kP133PortraitWidth,
                              kP133PortraitHeight));
  static_assert(validGeometry(480, 800, kP073PortraitWidth,
                              kP073PortraitHeight));
  static_assert(validGeometry(800, 480, kP073PortraitWidth,
                              kP073PortraitHeight));
  static_assert(!validGeometry(800, 480, kP133PortraitWidth,
                               kP133PortraitHeight));
  static_assert(!validGeometry(1200, 1600, kP073PortraitWidth,
                               kP073PortraitHeight));
  static_assert(knownGeometry(1200, 1600));
  static_assert(knownGeometry(800, 480));
  static_assert(!knownGeometry(800, 600));
  static_assert(rawSize(1200, 1600) == 960000);
  static_assert(rawSize(800, 480) == 192000);
  static_assert(highPixel(0x52) == 5);
  static_assert(lowPixel(0x52) == 2);
  static_assert(validPackedByte(0x05));
  static_assert(!validPackedByte(0x06));

  int minutes = -1;
  assert(parseClock("23:45", minutes) && minutes == 1425);
  assert(parseClock("00:00", minutes) && minutes == 0);
  assert(!parseClock("24:00", minutes));
  assert(!parseClock("7:00", minutes));
  assert(!parseClock(nullptr, minutes));

  assert(inNightWindow(23 * 60, 22 * 60, 7 * 60));
  assert(inNightWindow(6 * 60 + 59, 22 * 60, 7 * 60));
  assert(!inNightWindow(12 * 60, 22 * 60, 7 * 60));
  assert(inNightWindow(13 * 60, 12 * 60, 14 * 60));
  assert(!inNightWindow(14 * 60, 12 * 60, 14 * 60));
  assert(!inNightWindow(12 * 60, 12 * 60, 12 * 60));
  assert(secondsUntilNightEnd(23 * 60, 7 * 60) == 8U * 3600U);

  std::cout << "EE02/EE04 firmware core tests passed\n";
  return 0;
}
