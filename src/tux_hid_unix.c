/*
 * Tux Droid - Hid interface (only for unix)
 * Copyright (C) 2008 C2ME Sa <Acness : remi.jocaille@c2me.be>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2, or (at your option)
 * any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.
 */

/**
 * \file tux_hid_unix.c
 * \brief Tux HID functions.
 * \author remi.jocaille@c2me.be
 * \ingroup hid_interface
 */

#ifndef WIN32

#include <asm/types.h>
#include <fcntl.h>
#include <linux/hidraw.h>
#include <linux/input.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <dirent.h>
#include <string.h>

#include "tux_hid_unix.h"
#include "tux_misc.h"

static int tux_device_hdl = -1;
static char tux_device_path[256] = "";

/**
 * \brief Search the HID dongle in a "dev" path.
 * \param path Path how to search.
 * \param vendor_id Dongle vendor ID.
 * \param product_id Dongle product ID.
 * \return true or false
 */
static bool find_dongle_from_path(const char *path, int vendor_id,
                                  int product_id) {
  DIR *dir;
  struct dirent *dinfo;
  int fd = -1;
  char device_path[256] = "";
  struct hidraw_devinfo device_info;
  int err;

  dir = opendir(path);
  if (dir != NULL) {
    while ((dinfo = readdir(dir)) != NULL) {
      if (strncmp(dinfo->d_name, "hidraw", 6) == 0) {
        sprintf(device_path, "%s/%s", path, dinfo->d_name);

        if ((fd = open(device_path, O_RDWR)) >= 0) {
          err = ioctl(fd, HIDIOCGRAWINFO, &device_info);
          if (err == 0) {
            if ((device_info.vendor == vendor_id) &&
                ((device_info.product & 0xFFFF) == product_id)) {
              sprintf(tux_device_path, "%s", device_path);
              tux_device_hdl = fd;

              closedir(dir);

              return true;
            }
          }
          close(fd);
        }
      }
    }

    closedir(dir);
  }

  return false;
}

/**
 * \brief Check if the dongle is still plugged.
 * \return true or false.
 */
static bool check_device_still_plugged(void) {
  /* Simple check if fd is valid is not enough, but checking file existence
     helps if the device node disappears. With hidraw, if the device is
     unplugged, writes usually fail with ENODEV. */
  if (tux_device_hdl == -1) {
    return false;
  }
  return true;
}

/**
 * \brief Capture the HID dongle.
 * \param vendor_id Dongle vendor ID.
 * \param product_id Dongle product ID.
 * \return true or false.
 */
bool LIBLOCAL tux_hid_capture(int vendor_id, int product_id) {
  /* Scan /dev for hidraw devices */
  if (find_dongle_from_path("/dev", vendor_id, product_id)) {
    return true;
  }

  /* dongle not found */
  return false;
}

/**
 * \brief Release the access to the HID dongle.
 */
void LIBLOCAL tux_hid_release(void) {
  if (tux_device_hdl != -1) {
    close(tux_device_hdl);
    tux_device_hdl = -1;
  }
}

/**
 * \brief Write data to the HID dongle.
 * \param size Data size.
 * \param buffer Data to write.
 * \return The write success.
 */
bool LIBLOCAL tux_hid_write(int size, const char *buffer) {
  ssize_t res;
  char *new_buffer;

  if (!check_device_still_plugged()) {
    return false;
  }

  /* Prepend 0x00 for Report ID 0 */
  new_buffer = (char *)malloc(size + 1);
  if (new_buffer == NULL) {
    return false;
  }

  new_buffer[0] = 0x00;
  memcpy(new_buffer + 1, buffer, size);

  /* hidraw writes raw bytes */
  res = write(tux_device_hdl, new_buffer, size + 1);

  free(new_buffer);

  if (res < 0) {
    return false;
  }

  if (res != (size + 1)) {
    /* Partial write ? */
    return false;
  }

  return true;
}

/**
 * \brief Read data from the HID dongle.
 * \param size Data size.
 * \param buffer Data buffer.
 * \return The read success.
 */
bool LIBLOCAL tux_hid_read(int size, char *buffer) {
  ssize_t res;

  if (!check_device_still_plugged()) {
    return false;
  }

  /* hidraw reads raw bytes */
  res = read(tux_device_hdl, buffer, size);

  if (res < 0) {
    return false;
  }

  return true;
}

#endif /* Not WIN32 */
