/*
 * Tux Droid - Hid interface (libusb-1.0 backend)
 * This backend is used when hidraw is not available or preferred.
 */

#include "log.h"
#include "tux_hid_unix.h"
#include "tux_misc.h"
#include <libusb-1.0/libusb.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static libusb_context *ctx = NULL;
static libusb_device_handle *dev_handle = NULL;

#define TUX_INTERFACE 3
#define TUX_EP_IN 0x84
#define TUX_EP_OUT 0x05
#define TIMEOUT_MS 5000

bool LIBLOCAL tux_hid_capture(int vendor_id, int product_id) {
  int r;

  if (ctx == NULL) {
    r = libusb_init(&ctx);
    if (r < 0) {
      log_error("libusb_init error %d", r);
      return false;
    }
  }

  dev_handle = libusb_open_device_with_vid_pid(ctx, vendor_id, product_id);
  if (dev_handle == NULL) {
    log_error("Cannot open Tux device %04x:%04x", vendor_id, product_id);
    return false;
  }

  // Enable auto-detach if supported (libusb 1.0.16+)
  libusb_set_auto_detach_kernel_driver(dev_handle, 1);

  r = libusb_claim_interface(dev_handle, TUX_INTERFACE);
  if (r < 0) {
    log_error("Cannot claim interface %d: %d (%s)", TUX_INTERFACE, r,
              libusb_error_name(r));
    libusb_close(dev_handle);
    dev_handle = NULL;
    return false;
  }

  log_info("Tux device captured via libusb (Interface %d)", TUX_INTERFACE);
  return true;
}

void LIBLOCAL tux_hid_release(void) {
  if (dev_handle != NULL) {
    libusb_release_interface(dev_handle, TUX_INTERFACE);
    libusb_attach_kernel_driver(dev_handle, TUX_INTERFACE);
    libusb_close(dev_handle);
    dev_handle = NULL;
  }
  if (ctx != NULL) {
    libusb_exit(ctx);
    ctx = NULL;
  }
}

bool LIBLOCAL tux_hid_write(int size, const char *buffer) {
  int actual;
  int r;

  if (dev_handle == NULL)
    return false;

  r = libusb_interrupt_transfer(dev_handle, TUX_EP_OUT, (unsigned char *)buffer,
                                size, &actual, TIMEOUT_MS);
  if (r < 0) {
    log_error("libusb_interrupt_transfer OUT error %d (size %d)", r, size);
    return false;
  }

  return true;
}

bool LIBLOCAL tux_hid_read(int size, char *buffer) {
  int actual;
  int r;

  if (dev_handle == NULL)
    return false;

  r = libusb_interrupt_transfer(dev_handle, TUX_EP_IN, (unsigned char *)buffer,
                                size, &actual, TIMEOUT_MS);
  if (r < 0) {
    log_error("libusb_interrupt_transfer IN error %d", r);
    return false;
  }

  return true;
}
