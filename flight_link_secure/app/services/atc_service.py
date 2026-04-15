"""ATC flight plans, estimates, transfer, and management."""
from datetime import datetime

from app.extensions import db
from app.models import DefenseMessage, FlightPlan, TrackData, User
from modules.encryption import encrypt_track_data
from modules.flight_plan_form_io import parse_raw_to_form_fields
from modules.icao_validation import (
    normalize_icao_token,
    validate_aircraft_type,
    validate_callsign,
    validate_icao_airport,
)
from modules.flight_plan_parser import FlightPlanParser
from modules.validators import validate_atc_estimates


class TrackDeactivateError(Exception):
    """Base class for track deactivation failures."""


class TrackNotFoundError(TrackDeactivateError):
    """Raised when no ``track_data`` row exists for the given id."""


class TrackAlreadyInactiveError(TrackDeactivateError):
    """Raised when the track is not ``active`` (idempotent guard)."""


def deactivate_track(track_id, user):
    """
    Deactivate a single track: set status to terminated and completion time (UTC).

    ``user`` must be an ATC operator (caller enforces via ``@atc_required``).

    Returns:
        The updated :class:`TrackData` instance.

    Raises:
        TrackNotFoundError: No row for ``track_id``.
        TrackAlreadyInactiveError: ``status`` is not active (no DB changes).
    """
    if not isinstance(user, User) or not (user.is_atc() or user.is_admin()):
        raise TrackDeactivateError('Only ATC or admin users may deactivate tracks.')

    track = TrackData.query.get(track_id)
    if track is None:
        raise TrackNotFoundError(f'No track found with id {track_id}')

    if (track.status or '').lower() != 'active':
        raise TrackAlreadyInactiveError('Track is already inactive')

    track.status = 'terminated'
    track.completed_at = datetime.utcnow()
    db.session.commit()
    return track


def lookup_and_parse_flight_plan(callsign):
    """
    Retrieve flight plan by callsign and parse.
    Returns dict: parsed_data (dict or None), error (str or None), flight_plan_id (int or None).
    """
    callsign = normalize_icao_token(callsign)
    if not callsign:
        return {'parsed_data': None, 'error': 'Please enter a callsign', 'flight_plan_id': None}
    cs_ok, cs_msg = validate_callsign(callsign)
    if not cs_ok:
        return {'parsed_data': None, 'error': cs_msg, 'flight_plan_id': None}

    flight_plan = FlightPlan.query.filter_by(callsign=callsign).first()

    if not flight_plan:
        return {'parsed_data': None, 'error': f'Flight plan not found for callsign: {callsign}', 'flight_plan_id': None}

    parser = FlightPlanParser()
    parsed = parser.parse(flight_plan.raw_flight_plan)

    if parsed:
        return {
            'parsed_data': parsed.to_dict(),
            'error': None,
            'flight_plan_id': flight_plan.id,
        }

    return {
        'parsed_data': None,
        'error': f'Failed to parse flight plan for {callsign}. Errors: {", ".join(parser.get_errors())}',
        'flight_plan_id': None,
    }


def get_existing_active_track(flight_plan_id):
    return TrackData.query.filter_by(
        flight_plan_id=flight_plan_id,
        status='active'
    ).first()


def process_estimates_submission(parsed_data, flight_plan_id, user_id, eto, cfl, ssr):
    """
    Validate and create track when possible.
    Returns dict with keys:
      validation_result, submitted (bool), flash_error (str or None),
      log_ssr_block (tuple or None) for SSR duplicate case,
      log_track_created (tuple or None).
    """
    validation_result = validate_atc_estimates(eto, cfl, ssr)

    if not validation_result['valid']:
        return {
            'validation_result': validation_result,
            'submitted': False,
            'flash_error': None,
            'log_ssr_block': None,
            'log_track_created': None,
        }

    cs_ok, cs_msg = validate_callsign(parsed_data.get('callsign', ''))
    ac_ok, ac_msg = validate_aircraft_type(parsed_data.get('aircraft_type', ''))
    dep_ok, dep_msg = validate_icao_airport(parsed_data.get('departure', ''), "Departure")
    dest_ok, dest_msg = validate_icao_airport(parsed_data.get('destination', ''), "Destination")
    if not all((cs_ok, ac_ok, dep_ok, dest_ok)):
        validation_result['valid'] = False
        validation_result['errors'].extend(
            [
                msg
                for ok, msg in (
                    (cs_ok, cs_msg),
                    (ac_ok, ac_msg),
                    (dep_ok, dep_msg),
                    (dest_ok, dest_msg),
                )
                if not ok
            ]
        )
        return {
            'validation_result': validation_result,
            'submitted': False,
            'flash_error': 'Flight plan contains invalid ICAO identifiers and cannot be activated.',
            'log_ssr_block': None,
            'log_track_created': None,
        }

    existing_ssr_track = TrackData.query.filter_by(
        ssr=validation_result['ssr']['value'],
        status='active'
    ).first()

    if existing_ssr_track:
        validation_result['valid'] = False
        validation_result['ssr']['valid'] = False
        validation_result['ssr']['message'] = (
            f"SSR code {validation_result['ssr']['value']} is already assigned to active track "
            f"{existing_ssr_track.callsign}. Please enter a different code."
        )
        flash_msg = (
            f'SSR code {validation_result["ssr"]["value"]} is already in use by {existing_ssr_track.callsign}'
        )
        log_detail = f'SSR: {validation_result["ssr"]["value"]}, Callsign: {existing_ssr_track.callsign}'
        return {
            'validation_result': validation_result,
            'submitted': False,
            'flash_error': flash_msg,
            'log_ssr_block': ('SSR_DUPLICATE_BLOCKED', log_detail),
            'log_track_created': None,
        }

    track = TrackData(
        flight_plan_id=flight_plan_id,
        callsign=parsed_data['callsign'],
        aircraft_type=parsed_data['aircraft_type'],
        departure=parsed_data['departure'],
        destination=parsed_data['destination'],
        fir_entry=parsed_data['fir_entry'],
        speed=parsed_data['speed'],
        route=parsed_data.get('route', ''),
        eto_utc=validation_result['eto']['utc'],
        eto_pst=validation_result['eto']['pst'],
        cfl=validation_result['cfl']['value'],
        ssr=validation_result['ssr']['value'],
        status='active',
        sent_to_defense=False,
        created_by=user_id
    )

    db.session.add(track)
    db.session.commit()

    log_detail = f'Track ID: {track.id}, Callsign: {track.callsign}, SSR: {track.ssr}'
    return {
        'validation_result': validation_result,
        'submitted': True,
        'flash_error': None,
        'log_ssr_block': None,
        'log_track_created': ('TRACK_CREATED', log_detail),
        'new_track_id': track.id,
    }


def transfer_track_to_defense(track_id):
    """
    Encrypt track, create defense message, update track flags.
    Returns (track, defense_msg) or (None, None) if track missing.
    Caller clears session and redirects.
    """
    track = TrackData.query.get(track_id)
    if not track:
        return None, None

    transfer_data = {
        'track_id': track.id,
        'callsign': track.callsign,
        'aircraft_type': track.aircraft_type,
        'departure': track.departure,
        'destination': track.destination,
        'fir_entry': track.fir_entry,
        'speed': track.speed,
        'route': track.route,
        'eto_utc': track.eto_utc,
        'eto_pst': track.eto_pst,
        'cfl': track.cfl,
        'ssr': track.ssr,
        'status': track.status,
        'created_at': track.created_at.isoformat()
    }

    encrypted_data = encrypt_track_data(transfer_data)

    defense_msg = DefenseMessage(
        track_data_id=track.id,
        encrypted_data=encrypted_data,
        processed=False
    )

    track.sent_to_defense = True
    track.sent_at = datetime.utcnow()

    db.session.add(defense_msg)
    db.session.commit()

    return track, defense_msg


def _edit_flight_plan_template_ctx(flight_plan, raw_value: str):
    raw = (raw_value or "").strip()
    fields, _ = parse_raw_to_form_fields(raw)
    return {
        "flight_plan": flight_plan,
        "raw_value": raw,
        "initial_form": fields,
    }


def add_flight_plan_post(callsign, raw_flight_plan, replace_existing):
    """
    Process add/replace flight plan POST. Returns dict with:
      action: 'render' | 'redirect'
      template, context for render
      redirect_endpoint for redirect (symbolic key)
      flash_message, flash_category
      log_action, log_details (optional tuples)
    """
    def _add_ctx(extra=None):
        ctx = {
            'callsign': (callsign or '').strip().upper(),
            'initial_form': parse_raw_to_form_fields((raw_flight_plan or '').strip())[0],
        }
        if extra:
            ctx.update(extra)
        return ctx

    callsign = normalize_icao_token(callsign)
    raw_flight_plan = (raw_flight_plan or "").strip()
    if not callsign or not raw_flight_plan:
        return {
            'action': 'render',
            'template': 'atc/add_flight_plan.html',
            'context': _add_ctx(),
            'flash': ('All fields are required', 'error'),
        }

    cs_ok, cs_msg = validate_callsign(callsign)
    if not cs_ok:
        return {
            'action': 'render',
            'template': 'atc/add_flight_plan.html',
            'context': _add_ctx(),
            'flash': (cs_msg, 'error'),
        }

    parser = FlightPlanParser()
    parsed = parser.parse(raw_flight_plan)

    if not parsed:
        errors = ', '.join(parser.get_errors())
        return {
            'action': 'render',
            'template': 'atc/add_flight_plan.html',
            'context': _add_ctx(),
            'flash': (f'Flight plan validation failed: {errors}', 'error'),
        }

    parsed_data = parsed.to_dict()
    icao_callsign = parsed_data['callsign']
    if callsign != icao_callsign:
        return {
            'action': 'render',
            'template': 'atc/add_flight_plan.html',
            'context': _add_ctx(),
            'flash': (
                f'Callsign mismatch: You entered "{callsign}" but the ICAO flight plan contains '
                f'"{icao_callsign}". Please ensure both callsigns match.',
                'error'
            ),
        }

    ac_ok, ac_msg = validate_aircraft_type(parsed_data.get('aircraft_type', ''))
    dep_ok, dep_msg = validate_icao_airport(parsed_data.get('departure', ''), "Departure")
    dest_ok, dest_msg = validate_icao_airport(parsed_data.get('destination', ''), "Destination")
    if not all((ac_ok, dep_ok, dest_ok)):
        errs = [msg for ok, msg in ((ac_ok, ac_msg), (dep_ok, dep_msg), (dest_ok, dest_msg)) if not ok]
        return {
            'action': 'render',
            'template': 'atc/add_flight_plan.html',
            'context': _add_ctx(),
            'flash': (f'Flight plan validation failed: {"; ".join(errs)}', 'error'),
        }

    existing = FlightPlan.query.filter_by(callsign=callsign).first()
    if existing:
        active_tracks = TrackData.query.filter_by(
            flight_plan_id=existing.id,
            status='active'
        ).count()

        if active_tracks > 0:
            return {
                'action': 'render',
                'template': 'atc/add_flight_plan.html',
                'context': _add_ctx({
                    'duplicate_callsign': callsign,
                    'has_active_tracks': True,
                }),
                'flash': (
                    f'Cannot replace flight plan {callsign}: has {active_tracks} active track(s). '
                    'Complete the tracks first.',
                    'error'
                ),
            }

        if replace_existing:
            old_id = existing.id
            db.session.delete(existing)
            db.session.commit()
            logs = [('FLIGHT_PLAN_REPLACED', f'Replaced {callsign}, old ID: {old_id}')]
            new_plan = FlightPlan(
                callsign=callsign,
                raw_flight_plan=raw_flight_plan
            )
            db.session.add(new_plan)
            db.session.commit()
            logs.append(('FLIGHT_PLAN_ADDED', f'Callsign: {callsign}, ID: {new_plan.id}'))
            return {
                'action': 'redirect',
                'flash': (f'Flight plan {callsign} added successfully!', 'success'),
                'logs': logs,
            }
        else:
            return {
                'action': 'render',
                'template': 'atc/add_flight_plan.html',
                'context': _add_ctx({
                    'duplicate_callsign': callsign,
                    'duplicate_data': raw_flight_plan,
                    'has_active_tracks': False,
                }),
                'flash': None,
            }

    new_plan = FlightPlan(
        callsign=callsign,
        raw_flight_plan=raw_flight_plan
    )

    db.session.add(new_plan)
    db.session.commit()

    return {
        'action': 'redirect',
        'flash': (f'Flight plan {callsign} added successfully!', 'success'),
        'logs': [('FLIGHT_PLAN_ADDED', f'Callsign: {callsign}, ID: {new_plan.id}')],
    }


def edit_flight_plan_post(flight_plan, raw_flight_plan):
    """
    Update ``FlightPlan.raw_flight_plan`` in place after ICAO validation.

    Returns the same outcome shape as :func:`add_flight_plan_post`:
    ``action`` ('render' | 'redirect'), ``template``, ``context``, ``flash``, ``logs``.
    """
    if not (raw_flight_plan or '').strip():
        return {
            'action': 'render',
            'template': 'atc/edit_flight_plan.html',
            'context': _edit_flight_plan_template_ctx(flight_plan, ''),
            'flash': ('Flight plan text is required', 'error'),
        }

    active = TrackData.query.filter_by(
        flight_plan_id=flight_plan.id,
        status='active',
    ).count()
    if active > 0:
        return {
            'action': 'render',
            'template': 'atc/edit_flight_plan.html',
            'context': _edit_flight_plan_template_ctx(flight_plan, raw_flight_plan),
            'flash': (
                f'Cannot edit: {active} active track(s). Complete or deactivate tracks first.',
                'error',
            ),
        }

    parser = FlightPlanParser()
    parsed = parser.parse(raw_flight_plan)
    if not parsed:
        errors = ', '.join(parser.get_errors())
        return {
            'action': 'render',
            'template': 'atc/edit_flight_plan.html',
            'context': _edit_flight_plan_template_ctx(flight_plan, raw_flight_plan),
            'flash': (f'Flight plan validation failed: {errors}', 'error'),
        }

    parsed_data = parsed.to_dict()
    if parsed_data['callsign'] != flight_plan.callsign:
        return {
            'action': 'render',
            'template': 'atc/edit_flight_plan.html',
            'context': _edit_flight_plan_template_ctx(flight_plan, raw_flight_plan),
            'flash': (
                f'ICAO callsign in the plan is "{parsed_data["callsign"]}" but this record is '
                f'"{flight_plan.callsign}". The filed callsign must match.',
                'error',
            ),
        }

    ac_ok, ac_msg = validate_aircraft_type(parsed_data.get('aircraft_type', ''))
    dep_ok, dep_msg = validate_icao_airport(parsed_data.get('departure', ''), "Departure")
    dest_ok, dest_msg = validate_icao_airport(parsed_data.get('destination', ''), "Destination")
    if not all((ac_ok, dep_ok, dest_ok)):
        errs = [msg for ok, msg in ((ac_ok, ac_msg), (dep_ok, dep_msg), (dest_ok, dest_msg)) if not ok]
        return {
            'action': 'render',
            'template': 'atc/edit_flight_plan.html',
            'context': _edit_flight_plan_template_ctx(flight_plan, raw_flight_plan),
            'flash': (f'Flight plan validation failed: {"; ".join(errs)}', 'error'),
        }

    flight_plan.raw_flight_plan = raw_flight_plan.strip()
    db.session.commit()
    return {
        'action': 'redirect',
        'flash': (f'Flight plan {flight_plan.callsign} updated successfully.', 'success'),
        'logs': [('FLIGHT_PLAN_UPDATED', f'ID: {flight_plan.id}, Callsign: {flight_plan.callsign}')],
    }


def get_manage_flight_plans_context():
    flight_plans = FlightPlan.query.order_by(FlightPlan.created_at.desc()).all()
    plans_with_tracks = {}
    for plan in flight_plans:
        active_tracks = TrackData.query.filter_by(
            flight_plan_id=plan.id,
            status='active'
        ).count()
        plans_with_tracks[plan.id] = active_tracks > 0
    return {'flight_plans': flight_plans, 'plans_with_tracks': plans_with_tracks}


def delete_atc_flight_plan(flight_plan, terminate_tracks):
    """
    Terminate active tracks if requested, then delete plan.
    Returns dict: ok, flash_message, flash_category, redirect_with_warning (bool), log tuples.
    """
    plan_id = flight_plan.id
    active_tracks_list = TrackData.query.filter_by(
        flight_plan_id=plan_id,
        status='active'
    ).all()

    if active_tracks_list and not terminate_tracks:
        return {
            'ok': False,
            'redirect_warning': True,
            'flash': (
                f'Flight plan {flight_plan.callsign} has {len(active_tracks_list)} active track(s). '
                'Confirm termination to proceed.',
                'warning'
            ),
        }

    callsign = flight_plan.callsign
    logs = []

    if active_tracks_list and terminate_tracks:
        for track in active_tracks_list:
            track.status = 'terminated'
            track.completed_at = datetime.utcnow()
        db.session.commit()
        logs.append(('TRACKS_TERMINATED', f'Terminated {len(active_tracks_list)} track(s) for {callsign}'))

    db.session.delete(flight_plan)
    db.session.commit()
    logs.append(('FLIGHT_PLAN_DELETED', f'Callsign: {callsign}, ID: {plan_id}'))

    return {
        'ok': True,
        'redirect_warning': False,
        'flash': (f'Flight plan {callsign} deleted successfully', 'success'),
        'logs': logs,
    }


def get_api_flight_plan(callsign):
    """Return (success, payload_or_errors, http_code)."""
    callsign = normalize_icao_token(callsign)
    cs_ok, cs_msg = validate_callsign(callsign)
    if not cs_ok:
        return False, {'error': cs_msg}, 400

    flight_plan = FlightPlan.query.filter_by(callsign=callsign).first()

    if not flight_plan:
        return False, {'error': 'Flight plan not found'}, 404

    parser = FlightPlanParser()
    parsed = parser.parse(flight_plan.raw_flight_plan)

    if parsed:
        return True, parsed.to_dict(), 200

    return False, {
        'error': 'Failed to parse flight plan',
        'errors': parser.get_errors()
    }, 400
