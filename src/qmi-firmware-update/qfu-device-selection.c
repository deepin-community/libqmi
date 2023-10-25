/* -*- Mode: C; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * qmi-firmware-update -- Command line tool to update firmware in QMI devices
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Copyright (C) 2017 Zodiac Inflight Innovations
 * Copyright (C) 2017 Aleksander Morgado <aleksander@aleksander.es>
 */

#include <config.h>
#include <string.h>

#include <gio/gio.h>

#include <libqmi-glib.h>

#include "qfu-device-selection.h"
#include "qfu-helpers.h"

G_DEFINE_TYPE (QfuDeviceSelection, qfu_device_selection, G_TYPE_OBJECT)

struct _QfuDeviceSelectionPrivate {
    /* inputs */
    gchar   *preferred_devices[QFU_HELPERS_DEVICE_TYPE_LAST];
    guint16  preferred_vid;
    guint16  preferred_pid;
    guint    preferred_busnum;
    guint    preferred_devnum;

    /* sysfs path */
    gchar   *sysfs_path;
    /* peer port sysfs path */
    gchar   *peer_port;

#if defined WITH_UDEV
    /* generic udev monitor */
    QfuHelpersUdevGenericMonitor *monitor;
#endif
};

/******************************************************************************/

static GFile *
device_selection_get_single (QfuDeviceSelection   *self,
                             QfuHelpersDeviceType  device_type,
                             QfuHelpersDeviceMode  device_mode)
{
    GFile *first_selection = NULL;
    GFile *preferred_selection = NULL;
    GList *list, *l;
    gchar *path;

    g_debug ("[qfu,device-selection] single %s device requested in sysfs path '%s'",
             qfu_helpers_device_type_to_string (device_type),
             self->priv->sysfs_path);

    list = qfu_helpers_list_devices (device_type, device_mode, self->priv->sysfs_path);
    for (l = list; l; l = g_list_next (l)) {
        path = g_file_get_path (G_FILE (l->data));
        g_debug ("[qfu,device-selection]   device found: %s", path);
        if (!first_selection)
            first_selection = g_object_ref (l->data);
        if (!preferred_selection && !g_strcmp0 (path, self->priv->preferred_devices[device_type]))
            preferred_selection = g_object_ref (l->data);
        g_free (path);
    }
    g_list_free_full (list, g_object_unref);

    if (preferred_selection) {
        path = g_file_get_path (preferred_selection);
        g_debug ("[qfu,device-selection]   using preferred device: %s", path);
        g_free (path);
        if (first_selection)
            g_object_unref (first_selection);
        return preferred_selection;
    }

    if (first_selection) {
        path = g_file_get_path (first_selection);
        g_debug ("[qfu,device-selection]   using automatically selected device: %s", path);
        g_free (path);
        return first_selection;
    }

    g_debug ("[qfu,device-selection]   couldn't find any device to use");
    return NULL;
}

GFile *
qfu_device_selection_get_single_cdc_wdm (QfuDeviceSelection *self)
{
    return device_selection_get_single (self, QFU_HELPERS_DEVICE_TYPE_CDC_WDM, QFU_HELPERS_DEVICE_MODE_MODEM);
}

GFile *
qfu_device_selection_get_single_tty (QfuDeviceSelection   *self,
                                     QfuHelpersDeviceMode  mode)
{
    return device_selection_get_single (self, QFU_HELPERS_DEVICE_TYPE_TTY, mode);
}

/******************************************************************************/

static GList *
device_selection_get_multiple (QfuDeviceSelection   *self,
                               QfuHelpersDeviceType  device_type,
                               QfuHelpersDeviceMode  device_mode)
{
    GFile *preferred_selection = NULL;
    GList *list, *l;
    gchar *path;

    g_debug ("[qfu,device-selection] multiple %s devices requested in sysfs path '%s'",
             qfu_helpers_device_type_to_string (device_type),
             self->priv->sysfs_path);

    list = qfu_helpers_list_devices (device_type, device_mode, self->priv->sysfs_path);
    for (l = list; l; l = g_list_next (l)) {
        path = g_file_get_path (G_FILE (l->data));
        g_debug ("[qfu,device-selection]   device found: %s", path);
        if (!preferred_selection && !g_strcmp0 (path, self->priv->preferred_devices[device_type]))
            preferred_selection = g_object_ref (l->data);
        g_free (path);
    }

    /* If we have a preferred device selected, we will only include that one in the output list */
    if (preferred_selection) {
        path = g_file_get_path (preferred_selection);
        g_debug ("[qfu,device-selection]   using only preferred device: %s", path);
        g_free (path);
        g_list_free_full (list, g_object_unref);
        return g_list_append (NULL, preferred_selection);
    }

    if (list)
        return list;

    g_debug ("[qfu,device-selection]   couldn't find any device to use");
    return NULL;
}

GList *
qfu_device_selection_get_multiple_ttys (QfuDeviceSelection   *self,
                                        QfuHelpersDeviceMode  mode)
{
    return device_selection_get_multiple (self, QFU_HELPERS_DEVICE_TYPE_TTY, mode);
}

/******************************************************************************/

GFile *
qfu_device_selection_wait_for_cdc_wdm_finish (QfuDeviceSelection  *self,
                                              GAsyncResult        *res,
                                              GError             **error)
{
    return G_FILE (g_task_propagate_pointer (G_TASK (res), error));
}

GFile *
qfu_device_selection_wait_for_tty_finish (QfuDeviceSelection  *self,
                                          GAsyncResult        *res,
                                          GError             **error)
{
    return G_FILE (g_task_propagate_pointer (G_TASK (res), error));
}

static void
wait_for_device_ready (gpointer      unused,
                       GAsyncResult *res,
                       GTask        *task)
{
    GError *error = NULL;
    GFile  *file;

    file = qfu_helpers_wait_for_device_finish (res, &error);
    if (!file)
        g_task_return_error (task, error);
    else
        g_task_return_pointer (task, file, g_object_unref);
    g_object_unref (task);
}

void
qfu_device_selection_wait_for_cdc_wdm (QfuDeviceSelection  *self,
                                       GCancellable        *cancellable,
                                       GAsyncReadyCallback  callback,
                                       gpointer             user_data)
{
    GTask *task;

    task = g_task_new (self, cancellable, callback, user_data);
    qfu_helpers_wait_for_device (QFU_HELPERS_DEVICE_TYPE_CDC_WDM,
                                 QFU_HELPERS_DEVICE_MODE_MODEM,
                                 self->priv->sysfs_path,
                                 self->priv->peer_port,
                                 cancellable,
                                 (GAsyncReadyCallback) wait_for_device_ready,
                                 task);
}

void
qfu_device_selection_wait_for_tty (QfuDeviceSelection  *self,
                                   QfuHelpersDeviceMode mode,
                                   GCancellable        *cancellable,
                                   GAsyncReadyCallback  callback,
                                   gpointer             user_data)
{
    GTask *task;

    task = g_task_new (self, cancellable, callback, user_data);
    qfu_helpers_wait_for_device (QFU_HELPERS_DEVICE_TYPE_TTY,
                                 mode,
                                 self->priv->sysfs_path,
                                 self->priv->peer_port,
                                 cancellable,
                                 (GAsyncReadyCallback) wait_for_device_ready,
                                 task);
}

/******************************************************************************/

QfuDeviceSelection *
qfu_device_selection_new (const gchar  *preferred_cdc_wdm,
                          const gchar  *preferred_tty,
                          guint16       preferred_vid,
                          guint16       preferred_pid,
                          guint         preferred_busnum,
                          guint         preferred_devnum,
                          GError      **error)
{
    QfuDeviceSelection *self;
    guint               n_selections;

    /* Note: pid and busnum may be zero */
    n_selections = (!!preferred_cdc_wdm +
                    !!preferred_tty +
                    !!preferred_vid +
                    !!preferred_devnum);

    if (!n_selections) {
        g_set_error (error, G_IO_ERROR, G_IO_ERROR_FAILED,
                     "No device selected");
        return NULL;
    }

    if (n_selections > 1) {
        g_set_error (error, G_IO_ERROR, G_IO_ERROR_FAILED,
                     "Only one device selection option may be provided");
        return NULL;
    }

    /* Selection valid, create object */

    self = g_object_new (QFU_TYPE_DEVICE_SELECTION, NULL);

    /* Store inputs */
    self->priv->preferred_devices[QFU_HELPERS_DEVICE_TYPE_CDC_WDM] = g_strdup (preferred_cdc_wdm);
    self->priv->preferred_devices[QFU_HELPERS_DEVICE_TYPE_TTY]     = g_strdup (preferred_tty);
    self->priv->preferred_vid     = preferred_vid;
    self->priv->preferred_pid     = preferred_pid;
    self->priv->preferred_busnum  = preferred_busnum;
    self->priv->preferred_devnum  = preferred_devnum;

    /* Initialize sysfs path from inputs */
    if (preferred_vid || preferred_devnum)
        self->priv->sysfs_path = qfu_helpers_find_by_device_info (preferred_vid, preferred_pid, preferred_busnum, preferred_devnum, error);
    else if (preferred_cdc_wdm || preferred_tty)
        self->priv->sysfs_path = qfu_helpers_find_by_file_path (preferred_cdc_wdm ? preferred_cdc_wdm : preferred_tty, error);
    else
        g_assert_not_reached ();

    if (!self->priv->sysfs_path) {
        g_object_unref (self);
        return NULL;
    }

    /* look for a peer port */
    self->priv->peer_port = qfu_helpers_find_peer_port (self->priv->sysfs_path, error);

#if defined WITH_UDEV
    /* Initialize right away the generic udev monitor for this sysfs path */
    self->priv->monitor = qfu_helpers_udev_generic_monitor_new (self->priv->sysfs_path);
#endif

    return self;
}

static void
qfu_device_selection_init (QfuDeviceSelection *self)
{
    self->priv = G_TYPE_INSTANCE_GET_PRIVATE (self, QFU_TYPE_DEVICE_SELECTION, QfuDeviceSelectionPrivate);
}

static void
finalize (GObject *object)
{
    QfuDeviceSelection *self = QFU_DEVICE_SELECTION (object);
    guint               i;

#if defined WITH_UDEV
    if (self->priv->monitor)
        qfu_helpers_udev_generic_monitor_free (self->priv->monitor);
#endif

    g_free (self->priv->sysfs_path);
    g_free (self->priv->peer_port);

    for (i = 0; i < QFU_HELPERS_DEVICE_TYPE_LAST; i++)
        g_free (self->priv->preferred_devices[i]);

    G_OBJECT_CLASS (qfu_device_selection_parent_class)->finalize (object);
}

static void
qfu_device_selection_class_init (QfuDeviceSelectionClass *klass)
{
    GObjectClass *object_class = G_OBJECT_CLASS (klass);

    g_type_class_add_private (object_class, sizeof (QfuDeviceSelectionPrivate));

    object_class->finalize = finalize;
}
