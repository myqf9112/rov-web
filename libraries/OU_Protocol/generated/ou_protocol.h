/* AUTO-GENERATED, DO NOT EDIT, source: schema/protocol.yaml */
#ifndef OU_GENERATED_PROTOCOL_H
#define OU_GENERATED_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* frame constants (v0x04: AA 55 | ver | len | type | payload) */
#define OU_STX0 0xAA
#define OU_STX1 0x55
#define OU_PROTOCOL_VERSION 0x04
#define OU_FRAME_OVERHEAD 5

/* heartbeat, bidirectional at 1 Hz; armed determination = state >= ARMED and < CRITICAL */
#define OU_TYPE_HEARTBEAT 0x50
#define OU_HEARTBEAT_PAYLOAD_SIZE 4

/* system health + battery + link statistics + telemetry switches, 1 Hz */
#define OU_TYPE_SYSSTATUS 0x10
#define OU_SYSSTATUS_PAYLOAD_SIZE 49

/* command acknowledgement, matched with the command field of Command */
#define OU_TYPE_COMMANDACK 0x51
#define OU_COMMANDACK_PAYLOAD_SIZE 8

/* attitude + local NED position/velocity, 10–50 Hz; attitude and position share a timestamp */
#define OU_TYPE_POSENED 0x13
#define OU_POSENED_PAYLOAD_SIZE 52

/* EKF health/variance, 1 Hz; all variances are ×100 encoded */
#define OU_TYPE_EKFSTATUSREPORT 0x14
#define OU_EKFSTATUSREPORT_PAYLOAD_SIZE 7

/* artificial-horizon instrument readings, 1–5 Hz */
#define OU_TYPE_VFRHUD 0x15
#define OU_VFRHUD_PAYLOAD_SIZE 20

/* global lat/lon/altitude + NED velocity, 1 Hz */
#define OU_TYPE_GLOBALPOSITIONINT 0x16
#define OU_GLOBALPOSITIONINT_PAYLOAD_SIZE 28

/* GPS raw echo, disabled by default, enabled via CMD_SET_STREAM */
#define OU_TYPE_GPSRAWINT 0x18
#define OU_GPSRAWINT_PAYLOAD_SIZE 46

/* water depth / distance from bottom / water temperature (key Sub frame), 1–10 Hz */
#define OU_TYPE_WATERDEPTH 0x19
#define OU_WATERDEPTH_PAYLOAD_SIZE 30

/* ranging (collision-avoidance sonar), event /1 Hz */
#define OU_TYPE_DISTANCESENSOR 0x52
#define OU_DISTANCESENSOR_PAYLOAD_SIZE 23

/* six-axis velocity / angular-rate command, 10–50 Hz; stick value 0 hands that axis to the flight controller for stabilization; a non-incrementing sequence or an input timeout (~500 ms) triggers failsafe */
#define OU_TYPE_MANUALCONTROL 0x30
#define OU_MANUALCONTROL_PAYLOAD_SIZE 14

/* command frame; the flight controller answers with CommandAck; resend on 0.5–1 s timeout */
#define OU_TYPE_COMMAND 0x32
#define OU_COMMAND_PAYLOAD_SIZE 6

/* RC channel echo, disabled by default, enabled via CMD_SET_STREAM */
#define OU_TYPE_RCCHANNELS 0x1A
#define OU_RCCHANNELS_PAYLOAD_SIZE 42

/* actuator PWM output echo, disabled by default, enabled via CMD_SET_STREAM */
#define OU_TYPE_SERVOOUTPUTRAW 0x1B
#define OU_SERVOOUTPUTRAW_PAYLOAD_SIZE 37

/* write parameter */
#define OU_TYPE_PARAMSET 0x33
#define OU_PARAMSET_PAYLOAD_SIZE 21

/* parameter value read-back (the value actually stored by the flight controller, not an echo of the request) */
#define OU_TYPE_PARAMVALUE 0x1D
#define OU_PARAMVALUE_PAYLOAD_SIZE 25

/* Heartbeat field offsets */
#define OU_HEARTBEAT_MODE_OFFSET 0
#define OU_HEARTBEAT_SYSTEM_TYPE_OFFSET 1
#define OU_HEARTBEAT_FW_VERSION_OFFSET 2
#define OU_HEARTBEAT_SYSTEM_STATE_OFFSET 3
/* SysStatus field offsets */
#define OU_SYSSTATUS_SENSORS_PRESENT_OFFSET 0
#define OU_SYSSTATUS_SENSORS_ENABLED_OFFSET 4
#define OU_SYSSTATUS_SENSORS_HEALTH_OFFSET 8
#define OU_SYSSTATUS_LOAD_OFFSET 12
#define OU_SYSSTATUS_VOLTAGE_TOTAL_OFFSET 14
#define OU_SYSSTATUS_VOLTAGE_CELL_MAX_OFFSET 16
#define OU_SYSSTATUS_VOLTAGE_CELL_MIN_OFFSET 18
#define OU_SYSSTATUS_CURRENT_BATTERY_OFFSET 20
#define OU_SYSSTATUS_BATTERY_REMAINING_OFFSET 22
#define OU_SYSSTATUS_CURRENT_CONSUMED_OFFSET 23
#define OU_SYSSTATUS_BATTERY_TEMPERATURE_OFFSET 27
#define OU_SYSSTATUS_BATTERY_FAULT_BITMASK_OFFSET 29
#define OU_SYSSTATUS_DROP_RATE_COMM_OFFSET 33
#define OU_SYSSTATUS_ERRORS_COMM_OFFSET 35
#define OU_SYSSTATUS_ERRORS_COUNT_OFFSET 37
#define OU_SYSSTATUS_STREAM_MASK_OFFSET 45
/* CommandAck field offsets */
#define OU_COMMANDACK_COMMAND_OFFSET 0
#define OU_COMMANDACK_RESULT_OFFSET 2
#define OU_COMMANDACK_PROGRESS_OFFSET 3
#define OU_COMMANDACK_RESULT_PARAM2_OFFSET 4
/* PoseNed field offsets */
#define OU_POSENED_TIME_BOOT_MS_OFFSET 0
#define OU_POSENED_ROLL_OFFSET 4
#define OU_POSENED_PITCH_OFFSET 8
#define OU_POSENED_YAW_OFFSET 12
#define OU_POSENED_ROLLSPEED_OFFSET 16
#define OU_POSENED_PITCHSPEED_OFFSET 20
#define OU_POSENED_YAWSPEED_OFFSET 24
#define OU_POSENED_X_OFFSET 28
#define OU_POSENED_Y_OFFSET 32
#define OU_POSENED_Z_OFFSET 36
#define OU_POSENED_VX_OFFSET 40
#define OU_POSENED_VY_OFFSET 44
#define OU_POSENED_VZ_OFFSET 48
/* EkfStatusReport field offsets */
#define OU_EKFSTATUSREPORT_FLAGS_OFFSET 0
#define OU_EKFSTATUSREPORT_VELOCITY_VARIANCE_OFFSET 2
#define OU_EKFSTATUSREPORT_POS_HORIZ_VARIANCE_OFFSET 3
#define OU_EKFSTATUSREPORT_POS_VERT_VARIANCE_OFFSET 4
#define OU_EKFSTATUSREPORT_COMPASS_VARIANCE_OFFSET 5
#define OU_EKFSTATUSREPORT_TERRAIN_ALT_VARIANCE_OFFSET 6
/* VfrHud field offsets */
#define OU_VFRHUD_AIRSPEED_OFFSET 0
#define OU_VFRHUD_GROUNDSPEED_OFFSET 4
#define OU_VFRHUD_HEADING_OFFSET 8
#define OU_VFRHUD_THROTTLE_OFFSET 10
#define OU_VFRHUD_ALT_OFFSET 12
#define OU_VFRHUD_CLIMB_OFFSET 16
/* GlobalPositionInt field offsets */
#define OU_GLOBALPOSITIONINT_TIME_BOOT_MS_OFFSET 0
#define OU_GLOBALPOSITIONINT_LAT_OFFSET 4
#define OU_GLOBALPOSITIONINT_LON_OFFSET 8
#define OU_GLOBALPOSITIONINT_ALT_OFFSET 12
#define OU_GLOBALPOSITIONINT_RELATIVE_ALT_OFFSET 16
#define OU_GLOBALPOSITIONINT_VX_OFFSET 20
#define OU_GLOBALPOSITIONINT_VY_OFFSET 22
#define OU_GLOBALPOSITIONINT_VZ_OFFSET 24
#define OU_GLOBALPOSITIONINT_HDG_OFFSET 26
/* GpsRawInt field offsets */
#define OU_GPSRAWINT_TIME_USEC_OFFSET 0
#define OU_GPSRAWINT_FIX_TYPE_OFFSET 8
#define OU_GPSRAWINT_LAT_OFFSET 9
#define OU_GPSRAWINT_LON_OFFSET 13
#define OU_GPSRAWINT_ALT_OFFSET 17
#define OU_GPSRAWINT_EPH_OFFSET 21
#define OU_GPSRAWINT_EPV_OFFSET 23
#define OU_GPSRAWINT_VEL_OFFSET 25
#define OU_GPSRAWINT_COG_OFFSET 27
#define OU_GPSRAWINT_SATELLITES_VISIBLE_OFFSET 29
#define OU_GPSRAWINT_H_ACC_OFFSET 30
#define OU_GPSRAWINT_V_ACC_OFFSET 34
#define OU_GPSRAWINT_VEL_ACC_OFFSET 38
#define OU_GPSRAWINT_HDG_ACC_OFFSET 42
/* WaterDepth field offsets */
#define OU_WATERDEPTH_TIME_BOOT_MS_OFFSET 0
#define OU_WATERDEPTH_ID_OFFSET 4
#define OU_WATERDEPTH_HEALTHY_OFFSET 5
#define OU_WATERDEPTH_LAT_OFFSET 6
#define OU_WATERDEPTH_LNG_OFFSET 10
#define OU_WATERDEPTH_ALTITUDE_OFFSET 14
#define OU_WATERDEPTH_BOTTOM_DISTANCE_OFFSET 18
#define OU_WATERDEPTH_TERRAIN_HEIGHT_OFFSET 22
#define OU_WATERDEPTH_TEMPERATURE_OFFSET 26
/* DistanceSensor field offsets */
#define OU_DISTANCESENSOR_TIME_BOOT_MS_OFFSET 0
#define OU_DISTANCESENSOR_MIN_DISTANCE_OFFSET 4
#define OU_DISTANCESENSOR_MAX_DISTANCE_OFFSET 6
#define OU_DISTANCESENSOR_CURRENT_DISTANCE_OFFSET 8
#define OU_DISTANCESENSOR_TYPE_OFFSET 10
#define OU_DISTANCESENSOR_ID_OFFSET 11
#define OU_DISTANCESENSOR_ORIENTATION_OFFSET 12
#define OU_DISTANCESENSOR_COVARIANCE_OFFSET 13
#define OU_DISTANCESENSOR_HORIZONTAL_FOV_OFFSET 14
#define OU_DISTANCESENSOR_VERTICAL_FOV_OFFSET 18
#define OU_DISTANCESENSOR_SIGNAL_QUALITY_OFFSET 22
/* ManualControl field offsets */
#define OU_MANUALCONTROL_SEQUENCE_OFFSET 0
#define OU_MANUALCONTROL_X_OFFSET 2
#define OU_MANUALCONTROL_Y_OFFSET 4
#define OU_MANUALCONTROL_Z_OFFSET 6
#define OU_MANUALCONTROL_P_OFFSET 8
#define OU_MANUALCONTROL_R_OFFSET 10
#define OU_MANUALCONTROL_YAW_OFFSET 12
/* Command field offsets */
#define OU_COMMAND_COMMAND_OFFSET 0
#define OU_COMMAND_PARAM_OFFSET 2
/* RcChannels field offsets */
#define OU_RCCHANNELS_TIME_BOOT_MS_OFFSET 0
#define OU_RCCHANNELS_CHANCOUNT_OFFSET 4
#define OU_RCCHANNELS_CHAN_RAW_OFFSET 5
#define OU_RCCHANNELS_RSSI_OFFSET 41
/* ServoOutputRaw field offsets */
#define OU_SERVOOUTPUTRAW_TIME_BOOT_MS_OFFSET 0
#define OU_SERVOOUTPUTRAW_PORT_OFFSET 4
#define OU_SERVOOUTPUTRAW_SERVO_RAW_OFFSET 5
/* ParamSet field offsets */
#define OU_PARAMSET_PARAM_ID_OFFSET 0
#define OU_PARAMSET_PARAM_VALUE_OFFSET 16
#define OU_PARAMSET_PARAM_TYPE_OFFSET 20
/* ParamValue field offsets */
#define OU_PARAMVALUE_PARAM_ID_OFFSET 0
#define OU_PARAMVALUE_PARAM_VALUE_OFFSET 16
#define OU_PARAMVALUE_PARAM_TYPE_OFFSET 20
#define OU_PARAMVALUE_PARAM_COUNT_OFFSET 21
#define OU_PARAMVALUE_PARAM_INDEX_OFFSET 23

/* Mode enum */
#define OU_MODE_MANUAL 0
#define OU_MODE_AUTO 1
#define OU_MODE_RETURN 2
#define OU_MODE_HOLD 3
/* SystemState enum */
#define OU_SYSTEMSTATE_UNINIT 0
#define OU_SYSTEMSTATE_BOOT 1
#define OU_SYSTEMSTATE_CALIBRATING 2
#define OU_SYSTEMSTATE_STANDBY 3
#define OU_SYSTEMSTATE_ARMED 4
#define OU_SYSTEMSTATE_ACTIVE 5
#define OU_SYSTEMSTATE_CRITICAL 6
#define OU_SYSTEMSTATE_EMERGENCY 7
/* CommandId enum */
#define OU_COMMANDID_CMD_SET_MODE 1
#define OU_COMMANDID_CMD_ARM 2
#define OU_COMMANDID_CMD_GO_HOME 4
#define OU_COMMANDID_CMD_SET_STREAM 5
#define OU_COMMANDID_CMD_SET_PWM 6

/* heartbeat, bidirectional at 1 Hz; armed determination = state >= ARMED and < CRITICAL, payload 4 bytes */
typedef struct __attribute__((packed)) {
    uint8_t mode; /* current operating mode (authoritative source) */
    uint8_t system_type; /* bit0 role 0=robot 1=ground station; bit1..7 product index */
    uint8_t fw_version; /* sender firmware/SDK major version */
    uint8_t system_state; /* SystemState enum */
} Heartbeat;

_Static_assert(sizeof(Heartbeat) == 4, "Heartbeat size mismatch");

/* system health + battery + link statistics + telemetry switches, 1 Hz, payload 49 bytes */
typedef struct __attribute__((packed)) {
    uint32_t sensors_present; /* installed sensor bitmap */
    uint32_t sensors_enabled; /* enabled sensor bitmap */
    uint32_t sensors_health; /* sensor health bitmap */
    uint16_t load; /* CPU load %×10 */
    uint16_t voltage_total; /* battery total voltage, 65535=unknown */
    uint16_t voltage_cell_max; /* highest cell voltage, 65535=unknown */
    uint16_t voltage_cell_min; /* lowest cell voltage, 65535=unknown */
    int16_t current_battery; /* battery current, -1=unknown */
    int8_t battery_remaining; /* remaining percentage, -1=unknown */
    int32_t current_consumed; /* consumed capacity, -1=unknown */
    int16_t battery_temperature; /* battery temperature °C×100 */
    uint32_t battery_fault_bitmask; /* battery fault bitmap */
    uint16_t drop_rate_comm; /* packet drop rate %×100 */
    uint16_t errors_comm; /* communication error count */
    uint16_t errors_count[4]; /* system error count */
    uint32_t stream_mask; /* echoed-frame switch bitmap bit0=GpsRawInt bit1=RcChannels bit2=ServoOutputRaw */
} SysStatus;

_Static_assert(sizeof(SysStatus) == 49, "SysStatus size mismatch");

/* command acknowledgement, matched with the command field of Command, payload 8 bytes */
typedef struct __attribute__((packed)) {
    uint16_t command; /* acknowledged command number (Command enum) */
    uint8_t result; /* 0 accepted, 1 temporarily rejected, 2 rejected, 3 unsupported, 4 failed, 5 in progress */
    uint8_t progress; /* progress percentage */
    int32_t result_param2; /* additional result parameter */
} CommandAck;

_Static_assert(sizeof(CommandAck) == 8, "CommandAck size mismatch");

/* attitude + local NED position/velocity, 10–50 Hz; attitude and position share a timestamp, payload 52 bytes */
typedef struct __attribute__((packed)) {
    uint32_t time_boot_ms; /* time since boot (ms) */
    float roll; /* roll angle */
    float pitch; /* pitch angle */
    float yaw; /* yaw angle */
    float rollspeed; /* roll rate */
    float pitchspeed; /* pitch rate */
    float yawspeed; /* yaw rate */
    float x; /* north position (NED) */
    float y; /* east position (NED) */
    float z; /* down position (NED) */
    float vx; /* north velocity */
    float vy; /* east velocity */
    float vz; /* down velocity */
} PoseNed;

_Static_assert(sizeof(PoseNed) == 52, "PoseNed size mismatch");

/* EKF health/variance, 1 Hz; all variances are ×100 encoded, payload 7 bytes */
typedef struct __attribute__((packed)) {
    uint16_t flags; /* EKF health/fusion status bits */
    uint8_t velocity_variance; /* velocity variance ×100 */
    uint8_t pos_horiz_variance; /* horizontal position variance ×100 */
    uint8_t pos_vert_variance; /* vertical position variance ×100 */
    uint8_t compass_variance; /* compass variance ×100 */
    uint8_t terrain_alt_variance; /* terrain altitude variance ×100 */
} EkfStatusReport;

_Static_assert(sizeof(EkfStatusReport) == 7, "EkfStatusReport size mismatch");

/* artificial-horizon instrument readings, 1–5 Hz, payload 20 bytes */
typedef struct __attribute__((packed)) {
    float airspeed; /* water speed (0 when no sensor) */
    float groundspeed; /* ground speed */
    int16_t heading; /* heading */
    uint16_t throttle; /* throttle */
    float alt; /* altitude above bottom (synonymous with WaterDepth.altitude) */
    float climb; /* vertical velocity, positive up */
} VfrHud;

_Static_assert(sizeof(VfrHud) == 20, "VfrHud size mismatch");

/* global lat/lon/altitude + NED velocity, 1 Hz, payload 28 bytes */
typedef struct __attribute__((packed)) {
    uint32_t time_boot_ms; /* time since boot (ms) */
    int32_t lat; /* latitude ×1e7 */
    int32_t lon; /* longitude ×1e7 */
    int32_t alt; /* altitude AMSL */
    int32_t relative_alt; /* altitude relative to home */
    int16_t vx; /* north velocity */
    int16_t vy; /* east velocity */
    int16_t vz; /* down velocity */
    uint16_t hdg; /* heading ×100, 65535=unknown */
} GlobalPositionInt;

_Static_assert(sizeof(GlobalPositionInt) == 28, "GlobalPositionInt size mismatch");

/* GPS raw echo, disabled by default, enabled via CMD_SET_STREAM, payload 46 bytes */
typedef struct __attribute__((packed)) {
    uint64_t time_usec; /* microsecond timestamp */
    uint8_t fix_type; /* fix type enum */
    int32_t lat; /* latitude ×1e7 */
    int32_t lon; /* longitude ×1e7 */
    int32_t alt; /* altitude */
    uint16_t eph; /* horizontal accuracy ×100, 65535=unknown */
    uint16_t epv; /* vertical accuracy ×100, 65535=unknown */
    uint16_t vel; /* ground speed */
    uint16_t cog; /* heading ×100 */
    uint8_t satellites_visible; /* visible satellite count */
    uint32_t h_acc; /* horizontal accuracy */
    uint32_t v_acc; /* vertical accuracy */
    uint32_t vel_acc; /* velocity accuracy */
    uint32_t hdg_acc; /* heading accuracy */
} GpsRawInt;

_Static_assert(sizeof(GpsRawInt) == 46, "GpsRawInt size mismatch");

/* water depth / distance from bottom / water temperature (key Sub frame), 1–10 Hz, payload 30 bytes */
typedef struct __attribute__((packed)) {
    uint32_t time_boot_ms; /* time since boot (ms) */
    uint8_t id; /* sensor ID */
    uint8_t healthy; /* health status */
    int32_t lat; /* latitude ×1e7, optional */
    int32_t lng; /* longitude ×1e7, optional */
    float altitude; /* altitude above bottom */
    float bottom_distance; /* distance to bottom */
    float terrain_height; /* terrain height */
    float temperature; /* water temperature */
} WaterDepth;

_Static_assert(sizeof(WaterDepth) == 30, "WaterDepth size mismatch");

/* ranging (collision-avoidance sonar), event /1 Hz, payload 23 bytes */
typedef struct __attribute__((packed)) {
    uint32_t time_boot_ms; /* time since boot (ms) */
    uint16_t min_distance; /* range minimum */
    uint16_t max_distance; /* range maximum */
    uint16_t current_distance; /* current distance */
    uint8_t type; /* ranging type */
    uint8_t id; /* sensor ID */
    uint8_t orientation; /* orientation */
    uint8_t covariance; /* covariance, 255=unknown */
    float horizontal_fov; /* horizontal field of view */
    float vertical_fov; /* vertical field of view */
    uint8_t signal_quality; /* signal quality, 255=unknown */
} DistanceSensor;

_Static_assert(sizeof(DistanceSensor) == 23, "DistanceSensor size mismatch");

/* six-axis velocity / angular-rate command, 10–50 Hz; stick value 0 hands that axis to the flight controller for stabilization; a non-incrementing sequence or an input timeout (~500 ms) triggers failsafe, payload 14 bytes */
typedef struct __attribute__((packed)) {
    uint16_t sequence; /* incrementing sequence number, packet-loss/reorder detection */
    int16_t x; /* forward/backward velocity surge */
    int16_t y; /* lateral velocity sway */
    int16_t z; /* vertical velocity (heave) */
    int16_t p; /* pitch rate */
    int16_t r; /* roll rate */
    int16_t yaw; /* yaw rate */
} ManualControl;

_Static_assert(sizeof(ManualControl) == 14, "ManualControl size mismatch");

/* command frame; the flight controller answers with CommandAck; resend on 0.5–1 s timeout, payload 6 bytes */
typedef struct __attribute__((packed)) {
    uint16_t command; /* Command enum */
    uint32_t param; /* command parameter, interpreted per command definition */
} Command;

_Static_assert(sizeof(Command) == 6, "Command size mismatch");

/* RC channel echo, disabled by default, enabled via CMD_SET_STREAM, payload 42 bytes */
typedef struct __attribute__((packed)) {
    uint32_t time_boot_ms; /* time since boot (ms) */
    uint8_t chancount; /* valid channel count */
    uint16_t chan_raw[18]; /* raw values of 18 channels, 65535=invalid */
    uint8_t rssi; /* RC link strength, 255=unknown */
} RcChannels;

_Static_assert(sizeof(RcChannels) == 42, "RcChannels size mismatch");

/* actuator PWM output echo, disabled by default, enabled via CMD_SET_STREAM, payload 37 bytes */
typedef struct __attribute__((packed)) {
    uint32_t time_boot_ms; /* millisecond timestamp */
    uint8_t port; /* output port */
    uint16_t servo_raw[16]; /* 16-channel PWM output */
} ServoOutputRaw;

_Static_assert(sizeof(ServoOutputRaw) == 37, "ServoOutputRaw size mismatch");

/* write parameter, payload 21 bytes */
typedef struct __attribute__((packed)) {
    char param_id[16]; /* parameter name */
    float param_value; /* target value */
    uint8_t param_type; /* OU type enum */
} ParamSet;

_Static_assert(sizeof(ParamSet) == 21, "ParamSet size mismatch");

/* parameter value read-back (the value actually stored by the flight controller, not an echo of the request), payload 25 bytes */
typedef struct __attribute__((packed)) {
    char param_id[16]; /* parameter name */
    float param_value; /* actually stored value */
    uint8_t param_type; /* OU type enum */
    uint16_t param_count; /* total parameter count */
    uint16_t param_index; /* current index */
} ParamValue;

_Static_assert(sizeof(ParamValue) == 25, "ParamValue size mismatch");


/* ---------------------------------------------------------------------------
 * generative codec: full frame <-> payload, per-field little-endian expansion (consistent with the C++ template field order)
 * frame format: AA 55 | ver | len | type | payload
 * f32 uses IEEE-754 bit patterns.
 * bounds: encode requires frame_size >= 5 + payload; decode requires frame_size to match exactly,
 * and returns false if any of STX/ver/len/type does not match.
 * ------------------------------------------------------------------------- */
/* Heartbeat: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_Heartbeat(const Heartbeat* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_HEARTBEAT_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* mode */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->mode;
    }
    o += 1;
    /* system_type */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->system_type;
    }
    o += 1;
    /* fw_version */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->fw_version;
    }
    o += 1;
    /* system_state */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->system_state;
    }
    o += 1;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_HEARTBEAT;
    return true;
}

/* Heartbeat: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_Heartbeat(const uint8_t* frame, size_t frame_size, Heartbeat* out) {
    const size_t payload_size = OU_HEARTBEAT_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_HEARTBEAT) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* mode */
    for (size_t i = 0; i < 1; ++i) {
        out->mode = (uint8_t)p[o + i];
    }
    o += 1;
    /* system_type */
    for (size_t i = 0; i < 1; ++i) {
        out->system_type = (uint8_t)p[o + i];
    }
    o += 1;
    /* fw_version */
    for (size_t i = 0; i < 1; ++i) {
        out->fw_version = (uint8_t)p[o + i];
    }
    o += 1;
    /* system_state */
    for (size_t i = 0; i < 1; ++i) {
        out->system_state = (uint8_t)p[o + i];
    }
    o += 1;
    return true;
}

/* SysStatus: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_SysStatus(const SysStatus* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_SYSSTATUS_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* sensors_present */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->sensors_present;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* sensors_enabled */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->sensors_enabled;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* sensors_health */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->sensors_health;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* load */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->load;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* voltage_total */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->voltage_total;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* voltage_cell_max */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->voltage_cell_max;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* voltage_cell_min */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->voltage_cell_min;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* current_battery */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->current_battery;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* battery_remaining */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->battery_remaining;
    }
    o += 1;
    /* current_consumed */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->current_consumed;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* battery_temperature */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->battery_temperature;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* battery_fault_bitmask */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->battery_fault_bitmask;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* drop_rate_comm */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->drop_rate_comm;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* errors_comm */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->errors_comm;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* errors_count */
    for (size_t i = 0; i < 4; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->errors_count[i];
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 8;
    /* stream_mask */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->stream_mask;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_SYSSTATUS;
    return true;
}

/* SysStatus: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_SysStatus(const uint8_t* frame, size_t frame_size, SysStatus* out) {
    const size_t payload_size = OU_SYSSTATUS_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_SYSSTATUS) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* sensors_present */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->sensors_present = (uint32_t)v;
    }
    o += 4;
    /* sensors_enabled */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->sensors_enabled = (uint32_t)v;
    }
    o += 4;
    /* sensors_health */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->sensors_health = (uint32_t)v;
    }
    o += 4;
    /* load */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->load = (uint16_t)v;
    }
    o += 2;
    /* voltage_total */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->voltage_total = (uint16_t)v;
    }
    o += 2;
    /* voltage_cell_max */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->voltage_cell_max = (uint16_t)v;
    }
    o += 2;
    /* voltage_cell_min */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->voltage_cell_min = (uint16_t)v;
    }
    o += 2;
    /* current_battery */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->current_battery = (int16_t)v;
    }
    o += 2;
    /* battery_remaining */
    for (size_t i = 0; i < 1; ++i) {
        out->battery_remaining = (int8_t)p[o + i];
    }
    o += 1;
    /* current_consumed */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->current_consumed = (int32_t)v;
    }
    o += 4;
    /* battery_temperature */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->battery_temperature = (int16_t)v;
    }
    o += 2;
    /* battery_fault_bitmask */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->battery_fault_bitmask = (uint32_t)v;
    }
    o += 4;
    /* drop_rate_comm */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->drop_rate_comm = (uint16_t)v;
    }
    o += 2;
    /* errors_comm */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->errors_comm = (uint16_t)v;
    }
    o += 2;
    /* errors_count */
    for (size_t i = 0; i < 4; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->errors_count[i] = (uint16_t)v;
    }
    o += 8;
    /* stream_mask */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->stream_mask = (uint32_t)v;
    }
    o += 4;
    return true;
}

/* CommandAck: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_CommandAck(const CommandAck* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_COMMANDACK_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* command */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->command;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* result */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->result;
    }
    o += 1;
    /* progress */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->progress;
    }
    o += 1;
    /* result_param2 */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->result_param2;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_COMMANDACK;
    return true;
}

/* CommandAck: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_CommandAck(const uint8_t* frame, size_t frame_size, CommandAck* out) {
    const size_t payload_size = OU_COMMANDACK_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_COMMANDACK) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* command */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->command = (uint16_t)v;
    }
    o += 2;
    /* result */
    for (size_t i = 0; i < 1; ++i) {
        out->result = (uint8_t)p[o + i];
    }
    o += 1;
    /* progress */
    for (size_t i = 0; i < 1; ++i) {
        out->progress = (uint8_t)p[o + i];
    }
    o += 1;
    /* result_param2 */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->result_param2 = (int32_t)v;
    }
    o += 4;
    return true;
}

/* PoseNed: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_PoseNed(const PoseNed* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_POSENED_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->time_boot_ms;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* roll */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->roll;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* pitch */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->pitch;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* yaw */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->yaw;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* rollspeed */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->rollspeed;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* pitchspeed */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->pitchspeed;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* yawspeed */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->yawspeed;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* x */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->x;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* y */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->y;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* z */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->z;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* vx */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->vx;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* vy */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->vy;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* vz */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->vz;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_POSENED;
    return true;
}

/* PoseNed: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_PoseNed(const uint8_t* frame, size_t frame_size, PoseNed* out) {
    const size_t payload_size = OU_POSENED_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_POSENED) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->time_boot_ms = (uint32_t)v;
    }
    o += 4;
    /* roll */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->roll = fv;
    }
    o += 4;
    /* pitch */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->pitch = fv;
    }
    o += 4;
    /* yaw */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->yaw = fv;
    }
    o += 4;
    /* rollspeed */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->rollspeed = fv;
    }
    o += 4;
    /* pitchspeed */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->pitchspeed = fv;
    }
    o += 4;
    /* yawspeed */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->yawspeed = fv;
    }
    o += 4;
    /* x */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->x = fv;
    }
    o += 4;
    /* y */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->y = fv;
    }
    o += 4;
    /* z */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->z = fv;
    }
    o += 4;
    /* vx */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->vx = fv;
    }
    o += 4;
    /* vy */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->vy = fv;
    }
    o += 4;
    /* vz */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->vz = fv;
    }
    o += 4;
    return true;
}

/* EkfStatusReport: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_EkfStatusReport(const EkfStatusReport* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_EKFSTATUSREPORT_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* flags */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->flags;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* velocity_variance */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->velocity_variance;
    }
    o += 1;
    /* pos_horiz_variance */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->pos_horiz_variance;
    }
    o += 1;
    /* pos_vert_variance */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->pos_vert_variance;
    }
    o += 1;
    /* compass_variance */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->compass_variance;
    }
    o += 1;
    /* terrain_alt_variance */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->terrain_alt_variance;
    }
    o += 1;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_EKFSTATUSREPORT;
    return true;
}

/* EkfStatusReport: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_EkfStatusReport(const uint8_t* frame, size_t frame_size, EkfStatusReport* out) {
    const size_t payload_size = OU_EKFSTATUSREPORT_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_EKFSTATUSREPORT) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* flags */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->flags = (uint16_t)v;
    }
    o += 2;
    /* velocity_variance */
    for (size_t i = 0; i < 1; ++i) {
        out->velocity_variance = (uint8_t)p[o + i];
    }
    o += 1;
    /* pos_horiz_variance */
    for (size_t i = 0; i < 1; ++i) {
        out->pos_horiz_variance = (uint8_t)p[o + i];
    }
    o += 1;
    /* pos_vert_variance */
    for (size_t i = 0; i < 1; ++i) {
        out->pos_vert_variance = (uint8_t)p[o + i];
    }
    o += 1;
    /* compass_variance */
    for (size_t i = 0; i < 1; ++i) {
        out->compass_variance = (uint8_t)p[o + i];
    }
    o += 1;
    /* terrain_alt_variance */
    for (size_t i = 0; i < 1; ++i) {
        out->terrain_alt_variance = (uint8_t)p[o + i];
    }
    o += 1;
    return true;
}

/* VfrHud: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_VfrHud(const VfrHud* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_VFRHUD_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* airspeed */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->airspeed;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* groundspeed */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->groundspeed;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* heading */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->heading;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* throttle */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->throttle;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* alt */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->alt;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* climb */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->climb;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_VFRHUD;
    return true;
}

/* VfrHud: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_VfrHud(const uint8_t* frame, size_t frame_size, VfrHud* out) {
    const size_t payload_size = OU_VFRHUD_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_VFRHUD) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* airspeed */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->airspeed = fv;
    }
    o += 4;
    /* groundspeed */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->groundspeed = fv;
    }
    o += 4;
    /* heading */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->heading = (int16_t)v;
    }
    o += 2;
    /* throttle */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->throttle = (uint16_t)v;
    }
    o += 2;
    /* alt */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->alt = fv;
    }
    o += 4;
    /* climb */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->climb = fv;
    }
    o += 4;
    return true;
}

/* GlobalPositionInt: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_GlobalPositionInt(const GlobalPositionInt* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_GLOBALPOSITIONINT_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->time_boot_ms;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* lat */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->lat;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* lon */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->lon;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* alt */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->alt;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* relative_alt */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->relative_alt;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* vx */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->vx;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* vy */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->vy;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* vz */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->vz;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* hdg */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->hdg;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_GLOBALPOSITIONINT;
    return true;
}

/* GlobalPositionInt: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_GlobalPositionInt(const uint8_t* frame, size_t frame_size, GlobalPositionInt* out) {
    const size_t payload_size = OU_GLOBALPOSITIONINT_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_GLOBALPOSITIONINT) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->time_boot_ms = (uint32_t)v;
    }
    o += 4;
    /* lat */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->lat = (int32_t)v;
    }
    o += 4;
    /* lon */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->lon = (int32_t)v;
    }
    o += 4;
    /* alt */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->alt = (int32_t)v;
    }
    o += 4;
    /* relative_alt */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->relative_alt = (int32_t)v;
    }
    o += 4;
    /* vx */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->vx = (int16_t)v;
    }
    o += 2;
    /* vy */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->vy = (int16_t)v;
    }
    o += 2;
    /* vz */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->vz = (int16_t)v;
    }
    o += 2;
    /* hdg */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->hdg = (uint16_t)v;
    }
    o += 2;
    return true;
}

/* GpsRawInt: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_GpsRawInt(const GpsRawInt* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_GPSRAWINT_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_usec */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint64_t)pkt->time_usec;
        p[o + i * 8 + 0] = (uint8_t)(v >> 0);
        p[o + i * 8 + 1] = (uint8_t)(v >> 8);
        p[o + i * 8 + 2] = (uint8_t)(v >> 16);
        p[o + i * 8 + 3] = (uint8_t)(v >> 24);
        p[o + i * 8 + 4] = (uint8_t)(v >> 32);
        p[o + i * 8 + 5] = (uint8_t)(v >> 40);
        p[o + i * 8 + 6] = (uint8_t)(v >> 48);
        p[o + i * 8 + 7] = (uint8_t)(v >> 56);
    }
    o += 8;
    /* fix_type */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->fix_type;
    }
    o += 1;
    /* lat */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->lat;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* lon */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->lon;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* alt */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->alt;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* eph */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->eph;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* epv */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->epv;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* vel */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->vel;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* cog */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->cog;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* satellites_visible */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->satellites_visible;
    }
    o += 1;
    /* h_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->h_acc;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* v_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->v_acc;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* vel_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->vel_acc;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* hdg_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->hdg_acc;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_GPSRAWINT;
    return true;
}

/* GpsRawInt: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_GpsRawInt(const uint8_t* frame, size_t frame_size, GpsRawInt* out) {
    const size_t payload_size = OU_GPSRAWINT_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_GPSRAWINT) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_usec */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 8 + 0] << 0;
        v |= (uint64_t)p[o + i * 8 + 1] << 8;
        v |= (uint64_t)p[o + i * 8 + 2] << 16;
        v |= (uint64_t)p[o + i * 8 + 3] << 24;
        v |= (uint64_t)p[o + i * 8 + 4] << 32;
        v |= (uint64_t)p[o + i * 8 + 5] << 40;
        v |= (uint64_t)p[o + i * 8 + 6] << 48;
        v |= (uint64_t)p[o + i * 8 + 7] << 56;
        out->time_usec = (uint64_t)v;
    }
    o += 8;
    /* fix_type */
    for (size_t i = 0; i < 1; ++i) {
        out->fix_type = (uint8_t)p[o + i];
    }
    o += 1;
    /* lat */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->lat = (int32_t)v;
    }
    o += 4;
    /* lon */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->lon = (int32_t)v;
    }
    o += 4;
    /* alt */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->alt = (int32_t)v;
    }
    o += 4;
    /* eph */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->eph = (uint16_t)v;
    }
    o += 2;
    /* epv */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->epv = (uint16_t)v;
    }
    o += 2;
    /* vel */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->vel = (uint16_t)v;
    }
    o += 2;
    /* cog */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->cog = (uint16_t)v;
    }
    o += 2;
    /* satellites_visible */
    for (size_t i = 0; i < 1; ++i) {
        out->satellites_visible = (uint8_t)p[o + i];
    }
    o += 1;
    /* h_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->h_acc = (uint32_t)v;
    }
    o += 4;
    /* v_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->v_acc = (uint32_t)v;
    }
    o += 4;
    /* vel_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->vel_acc = (uint32_t)v;
    }
    o += 4;
    /* hdg_acc */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->hdg_acc = (uint32_t)v;
    }
    o += 4;
    return true;
}

/* WaterDepth: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_WaterDepth(const WaterDepth* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_WATERDEPTH_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->time_boot_ms;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* id */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->id;
    }
    o += 1;
    /* healthy */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->healthy;
    }
    o += 1;
    /* lat */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->lat;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* lng */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->lng;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* altitude */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->altitude;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* bottom_distance */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->bottom_distance;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* terrain_height */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->terrain_height;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* temperature */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->temperature;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_WATERDEPTH;
    return true;
}

/* WaterDepth: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_WaterDepth(const uint8_t* frame, size_t frame_size, WaterDepth* out) {
    const size_t payload_size = OU_WATERDEPTH_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_WATERDEPTH) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->time_boot_ms = (uint32_t)v;
    }
    o += 4;
    /* id */
    for (size_t i = 0; i < 1; ++i) {
        out->id = (uint8_t)p[o + i];
    }
    o += 1;
    /* healthy */
    for (size_t i = 0; i < 1; ++i) {
        out->healthy = (uint8_t)p[o + i];
    }
    o += 1;
    /* lat */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->lat = (int32_t)v;
    }
    o += 4;
    /* lng */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->lng = (int32_t)v;
    }
    o += 4;
    /* altitude */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->altitude = fv;
    }
    o += 4;
    /* bottom_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->bottom_distance = fv;
    }
    o += 4;
    /* terrain_height */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->terrain_height = fv;
    }
    o += 4;
    /* temperature */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->temperature = fv;
    }
    o += 4;
    return true;
}

/* DistanceSensor: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_DistanceSensor(const DistanceSensor* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_DISTANCESENSOR_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->time_boot_ms;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* min_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->min_distance;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* max_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->max_distance;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* current_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->current_distance;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* type */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->type;
    }
    o += 1;
    /* id */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->id;
    }
    o += 1;
    /* orientation */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->orientation;
    }
    o += 1;
    /* covariance */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->covariance;
    }
    o += 1;
    /* horizontal_fov */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->horizontal_fov;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* vertical_fov */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->vertical_fov;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* signal_quality */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->signal_quality;
    }
    o += 1;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_DISTANCESENSOR;
    return true;
}

/* DistanceSensor: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_DistanceSensor(const uint8_t* frame, size_t frame_size, DistanceSensor* out) {
    const size_t payload_size = OU_DISTANCESENSOR_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_DISTANCESENSOR) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->time_boot_ms = (uint32_t)v;
    }
    o += 4;
    /* min_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->min_distance = (uint16_t)v;
    }
    o += 2;
    /* max_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->max_distance = (uint16_t)v;
    }
    o += 2;
    /* current_distance */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->current_distance = (uint16_t)v;
    }
    o += 2;
    /* type */
    for (size_t i = 0; i < 1; ++i) {
        out->type = (uint8_t)p[o + i];
    }
    o += 1;
    /* id */
    for (size_t i = 0; i < 1; ++i) {
        out->id = (uint8_t)p[o + i];
    }
    o += 1;
    /* orientation */
    for (size_t i = 0; i < 1; ++i) {
        out->orientation = (uint8_t)p[o + i];
    }
    o += 1;
    /* covariance */
    for (size_t i = 0; i < 1; ++i) {
        out->covariance = (uint8_t)p[o + i];
    }
    o += 1;
    /* horizontal_fov */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->horizontal_fov = fv;
    }
    o += 4;
    /* vertical_fov */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->vertical_fov = fv;
    }
    o += 4;
    /* signal_quality */
    for (size_t i = 0; i < 1; ++i) {
        out->signal_quality = (uint8_t)p[o + i];
    }
    o += 1;
    return true;
}

/* ManualControl: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_ManualControl(const ManualControl* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_MANUALCONTROL_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* sequence */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->sequence;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* x */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->x;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* y */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->y;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* z */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->z;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* p */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->p;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* r */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->r;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* yaw */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->yaw;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_MANUALCONTROL;
    return true;
}

/* ManualControl: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_ManualControl(const uint8_t* frame, size_t frame_size, ManualControl* out) {
    const size_t payload_size = OU_MANUALCONTROL_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_MANUALCONTROL) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* sequence */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->sequence = (uint16_t)v;
    }
    o += 2;
    /* x */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->x = (int16_t)v;
    }
    o += 2;
    /* y */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->y = (int16_t)v;
    }
    o += 2;
    /* z */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->z = (int16_t)v;
    }
    o += 2;
    /* p */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->p = (int16_t)v;
    }
    o += 2;
    /* r */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->r = (int16_t)v;
    }
    o += 2;
    /* yaw */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->yaw = (int16_t)v;
    }
    o += 2;
    return true;
}

/* Command: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_Command(const Command* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_COMMAND_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* command */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->command;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* param */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->param;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_COMMAND;
    return true;
}

/* Command: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_Command(const uint8_t* frame, size_t frame_size, Command* out) {
    const size_t payload_size = OU_COMMAND_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_COMMAND) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* command */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->command = (uint16_t)v;
    }
    o += 2;
    /* param */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->param = (uint32_t)v;
    }
    o += 4;
    return true;
}

/* RcChannels: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_RcChannels(const RcChannels* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_RCCHANNELS_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->time_boot_ms;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* chancount */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->chancount;
    }
    o += 1;
    /* chan_raw */
    for (size_t i = 0; i < 18; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->chan_raw[i];
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 36;
    /* rssi */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->rssi;
    }
    o += 1;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_RCCHANNELS;
    return true;
}

/* RcChannels: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_RcChannels(const uint8_t* frame, size_t frame_size, RcChannels* out) {
    const size_t payload_size = OU_RCCHANNELS_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_RCCHANNELS) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->time_boot_ms = (uint32_t)v;
    }
    o += 4;
    /* chancount */
    for (size_t i = 0; i < 1; ++i) {
        out->chancount = (uint8_t)p[o + i];
    }
    o += 1;
    /* chan_raw */
    for (size_t i = 0; i < 18; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->chan_raw[i] = (uint16_t)v;
    }
    o += 36;
    /* rssi */
    for (size_t i = 0; i < 1; ++i) {
        out->rssi = (uint8_t)p[o + i];
    }
    o += 1;
    return true;
}

/* ServoOutputRaw: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_ServoOutputRaw(const ServoOutputRaw* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_SERVOOUTPUTRAW_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint32_t)pkt->time_boot_ms;
        p[o + i * 4 + 0] = (uint8_t)(v >> 0);
        p[o + i * 4 + 1] = (uint8_t)(v >> 8);
        p[o + i * 4 + 2] = (uint8_t)(v >> 16);
        p[o + i * 4 + 3] = (uint8_t)(v >> 24);
    }
    o += 4;
    /* port */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->port;
    }
    o += 1;
    /* servo_raw */
    for (size_t i = 0; i < 16; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->servo_raw[i];
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 32;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_SERVOOUTPUTRAW;
    return true;
}

/* ServoOutputRaw: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_ServoOutputRaw(const uint8_t* frame, size_t frame_size, ServoOutputRaw* out) {
    const size_t payload_size = OU_SERVOOUTPUTRAW_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_SERVOOUTPUTRAW) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* time_boot_ms */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 4 + 0] << 0;
        v |= (uint64_t)p[o + i * 4 + 1] << 8;
        v |= (uint64_t)p[o + i * 4 + 2] << 16;
        v |= (uint64_t)p[o + i * 4 + 3] << 24;
        out->time_boot_ms = (uint32_t)v;
    }
    o += 4;
    /* port */
    for (size_t i = 0; i < 1; ++i) {
        out->port = (uint8_t)p[o + i];
    }
    o += 1;
    /* servo_raw */
    for (size_t i = 0; i < 16; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->servo_raw[i] = (uint16_t)v;
    }
    o += 32;
    return true;
}

/* ParamSet: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_ParamSet(const ParamSet* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_PARAMSET_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* param_id */
    for (size_t i = 0; i < 16; ++i) {
        p[o + i] = (uint8_t)pkt->param_id[i];
    }
    o += 16;
    /* param_value */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->param_value;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* param_type */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->param_type;
    }
    o += 1;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_PARAMSET;
    return true;
}

/* ParamSet: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_ParamSet(const uint8_t* frame, size_t frame_size, ParamSet* out) {
    const size_t payload_size = OU_PARAMSET_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_PARAMSET) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* param_id */
    for (size_t i = 0; i < 16; ++i) {
        out->param_id[i] = (char)p[o + i];
    }
    o += 16;
    /* param_value */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->param_value = fv;
    }
    o += 4;
    /* param_type */
    for (size_t i = 0; i < 1; ++i) {
        out->param_type = (uint8_t)p[o + i];
    }
    o += 1;
    return true;
}

/* ParamValue: encode (assemble full frame); returns false if frame_size is insufficient */
static inline bool encode_ParamValue(const ParamValue* pkt, uint8_t* frame, size_t frame_size) {
    const size_t payload_size = OU_PARAMVALUE_PAYLOAD_SIZE;
    if (pkt == NULL || frame == NULL) return false;
    if (frame_size < payload_size + OU_FRAME_OVERHEAD) return false;
    uint8_t* p = frame + 5;
    size_t o = 0;
    /* param_id */
    for (size_t i = 0; i < 16; ++i) {
        p[o + i] = (uint8_t)pkt->param_id[i];
    }
    o += 16;
    /* param_value */
    for (size_t i = 0; i < 1; ++i) {
        float fv = pkt->param_value;
        uint32_t bits;
        memcpy(&bits, &fv, sizeof(bits));
        p[o + i * 4 + 0] = (uint8_t)(bits >> 0);
        p[o + i * 4 + 1] = (uint8_t)(bits >> 8);
        p[o + i * 4 + 2] = (uint8_t)(bits >> 16);
        p[o + i * 4 + 3] = (uint8_t)(bits >> 24);
    }
    o += 4;
    /* param_type */
    for (size_t i = 0; i < 1; ++i) {
        p[o + i] = (uint8_t)pkt->param_type;
    }
    o += 1;
    /* param_count */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->param_count;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    /* param_index */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = (uint64_t)(uint16_t)pkt->param_index;
        p[o + i * 2 + 0] = (uint8_t)(v >> 0);
        p[o + i * 2 + 1] = (uint8_t)(v >> 8);
    }
    o += 2;
    frame[0] = OU_STX0;
    frame[1] = OU_STX1;
    frame[2] = OU_PROTOCOL_VERSION;
    frame[3] = (uint8_t)payload_size;
    frame[4] = OU_TYPE_PARAMVALUE;
    return true;
}

/* ParamValue: decode (full frame -> payload); returns false on check or length mismatch */
static inline bool decode_ParamValue(const uint8_t* frame, size_t frame_size, ParamValue* out) {
    const size_t payload_size = OU_PARAMVALUE_PAYLOAD_SIZE;
    const size_t total = payload_size + OU_FRAME_OVERHEAD;
    if (frame == NULL || out == NULL) return false;
    if (frame_size != total) return false;
    if (frame[0] != OU_STX0 || frame[1] != OU_STX1) return false;
    if (frame[2] != OU_PROTOCOL_VERSION) return false;
    if (frame[3] != (uint8_t)payload_size) return false;
    if (frame[4] != OU_TYPE_PARAMVALUE) return false;
    const uint8_t* p = frame + 5;
    size_t o = 0;
    /* param_id */
    for (size_t i = 0; i < 16; ++i) {
        out->param_id[i] = (char)p[o + i];
    }
    o += 16;
    /* param_value */
    for (size_t i = 0; i < 1; ++i) {
        uint32_t bits = 0;
        bits |= (uint32_t)p[o + i * 4 + 0] << 0;
        bits |= (uint32_t)p[o + i * 4 + 1] << 8;
        bits |= (uint32_t)p[o + i * 4 + 2] << 16;
        bits |= (uint32_t)p[o + i * 4 + 3] << 24;
        float fv;
        memcpy(&fv, &bits, sizeof(fv));
        out->param_value = fv;
    }
    o += 4;
    /* param_type */
    for (size_t i = 0; i < 1; ++i) {
        out->param_type = (uint8_t)p[o + i];
    }
    o += 1;
    /* param_count */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->param_count = (uint16_t)v;
    }
    o += 2;
    /* param_index */
    for (size_t i = 0; i < 1; ++i) {
        uint64_t v = 0;
        v |= (uint64_t)p[o + i * 2 + 0] << 0;
        v |= (uint64_t)p[o + i * 2 + 1] << 8;
        out->param_index = (uint16_t)v;
    }
    o += 2;
    return true;
}

#ifdef __cplusplus
}
#endif

#endif /* OU_GENERATED_PROTOCOL_H */