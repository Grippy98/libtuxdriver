#include "log.h"
#include "tux_cmd_parser.h"
#include "tux_descriptor.h"
#include "tux_hw_status.h"
#include "tux_sw_status.h"
#include "tux_usb.h"
#include "tux_user_inputs.h"
#include "version.h"
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>

static bool driver_initialized = false;

// Forward declarations are already in the headers or handled by callbacks

// We need reference to existing callbacks
extern void on_frame(const unsigned char *data);
extern void on_rf_state(unsigned char state);
extern void on_usb_connect(void);
extern void on_usb_disconnect(void);
extern void on_read_loop_cycle_complete(void);

/**
 * Initialize the driver without starting the blocking loop.
 */
__attribute__((visibility("default"))) void TuxDrv_InitNonBlocking(void) {
  if (driver_initialized) {
    return;
  }

  printf("libtuxdriver_%d.%d.%d-r%d (non-blocking mode)\n\n", VER_MAJOR,
         VER_MINOR, VER_UPDATE, VER_REVISION);

  tux_usb_init_module();
  tux_usb_set_frame_callback(on_frame);
  tux_usb_set_rf_state_callback(on_rf_state);
  tux_usb_set_connect_dongle_callback(on_usb_connect);
  tux_usb_set_disconnect_dongle_callback(on_usb_disconnect);
  tux_usb_set_loop_cycle_complete_callback(on_read_loop_cycle_complete);

  tux_descriptor_init();
  tux_hw_status_init();
  tux_sw_status_init();
  tux_user_inputs_init();
  tux_cmd_parser_init();

  driver_initialized = true;

  // Attempt initial connection
  tux_usb_capture();
}

/**
 * Poll once for USB events. Call this periodically from your event loop.
 */
__attribute__((visibility("default"))) void TuxDrv_PollOnce(void) {
  unsigned char data[64];

  if (!driver_initialized) {
    return;
  }

  if (tux_usb_connected()) {
    // Read data (this will send status request and process response via
    // callbacks)
    tux_usb_read(data);

    // Notify cycle complete
    on_read_loop_cycle_complete();
  } else {
    // Try to reconnect
    tux_usb_capture();
  }
}

/**
 * Stop the non-blocking driver.
 */
__attribute__((visibility("default"))) void TuxDrv_StopNonBlocking(void) {
  if (!driver_initialized) {
    return;
  }

  if (tux_usb_connected()) {
    tux_usb_release();
  }
  tux_usb_exit_module();
  driver_initialized = false;
}
