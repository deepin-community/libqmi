/* -*- Mode: C; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */

/*
 * libqmi-glib -- GLib/GIO based library to control QMI devices
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
 * Boston, MA 02110-1301 USA.
 *
 * Copyright (C) 2012-2015 Dan Williams <dcbw@redhat.com>
 * Copyright (C) 2012-2017 Aleksander Morgado <aleksander@aleksander.es>
 * Copyright (C) 1999,2000 Erik Walthinsen <omega@cse.ogi.edu>
 * Copyright (C) 2000 Wim Taymans <wtay@chello.be>
 * Copyright (C) 2002 Thomas Vander Stichele <thomas@apestaart.org>

 */

#ifndef _LIBQMI_GLIB_QMI_UTILS_H_
#define _LIBQMI_GLIB_QMI_UTILS_H_

#if !defined (__LIBQMI_GLIB_H_INSIDE__) && !defined (LIBQMI_GLIB_COMPILATION)
#error "Only <libqmi-glib.h> can be included directly."
#endif

#include <glib.h>

G_BEGIN_DECLS

/**
 * QmiEndian:
 * @QMI_ENDIAN_LITTLE: Little endian.
 * @QMI_ENDIAN_BIG: Big endian.
 *
 * Type of endianness
 *
 * Since: 1.0
 */
typedef enum {
    QMI_ENDIAN_LITTLE = 0,
    QMI_ENDIAN_BIG    = 1
} QmiEndian;

/* Enabling/Disabling traces */

/**
 * qmi_utils_get_traces_enabled:
 *
 * Checks whether QMI message traces are currently enabled.
 *
 * Returns: %TRUE if traces are enabled, %FALSE otherwise.
 *
 * Since: 1.0
 */
gboolean qmi_utils_get_traces_enabled (void);

/**
 * qmi_utils_set_traces_enabled:
 * @enabled: %TRUE to enable traces, %FALSE to disable them.
 *
 * Sets whether QMI message traces are enabled or disabled.
 *
 * Since: 1.0
 */
void qmi_utils_set_traces_enabled (gboolean enabled);

G_END_DECLS

#endif /* _LIBQMI_GLIB_QMI_UTILS_H_ */
