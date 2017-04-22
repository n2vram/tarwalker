tarwalker
=========

Summary
-------
 
This library provides two (2) classes for scanning files that can be provided as filenames, directory names or archive files.


Installation
------------
Install the package using **pip**, eg:

     sudo pip install tarwalker

Or for a specific version:

     sudo python3 -m pip install pynumparser

*Tarwalker*
----------------

Allowed inputs are comprised of one (1) or more subsequences separated by a comma (",").
Subsequences can be simple numbers or number ranges with or without a *stride* value.

* Simple number values yield a single value.

* A range is expressed as two (2) number values separated by a dash/hyphen ("-"). A range will
  yield multiple values (usually) **including both boundary values**. Numbers in the range differ by
  the optional *stride* value, which defaults to **1**.

  * The lower and upper range values are separated by a single dash/hyphen, except if the upper
    range value is negative (eg: "-5--3").  The upper range value must be greater or equal
    to the lower range value.

  * The optional *stride* value is separated from the second range value with a forward slash ("/").

* By default numbers are of **int** type, but if constructed with the parameter
  (*numtype=float*) the inputs are parsed as floating point numbers *with a* **dot** *for a
  decimial point*, since the comma is used for subsequence separator.

* If the difference between the limits is not an even mulitiple of the *stride* value, then the
  second range will *not* be included in the result.

* The parser has a *contains* method, which can be used to for a number versus a text range.


**Exceptions**:
^^^^^^^^^^^^^^^
* The constructor **limits** parameter must be either *None* or a 2-tuple; the tuple values must
  be *None* or a value of **numtype**, and:

  * If neither are *None*, then the **limits[0]** value must be less than the **limits[1]** value;
    or a ValueError is raised **by the constructor**. 

  * If **limits[0]** is not *None*, then if any value is less than **limits[0]** a ValueError is
    raised.

  * If **limits[1]** is not *None*, then if any value is greater than **limits[1]** a ValueError is
    raised.

* If any input cannot be parsed as a valid number of given the **numtype** a ValueError is raised.

* If the second range value is less than the first range value (eg: **"8-5"**) a ValueError is
  raised.

* If any floating point number equates to positive or negative infinity (eg: **"1e9999"**) a
  ValueError is raised.

* Negative *stride* values are not currently allowed  (but please upvote the enhancement via GitHub
  if you need it).

* If the *stride* value is zero (0) a ValueError is raised, even if the upper and lower limit values
  are equal.

* When used within **argparse.ArgumentParser** any strings that begin with a dash/hyphen values must
  be part of the flag argument (except for simple integer values).  For example:

    * This would give a parse error:  **foobar --arg -8-12 -N -5e8**

    * Whereas, this could be valid:   **foobar --arg=-8-12 -N-5e8**

If used within an **argparse.ArgumentParser**, the ValueError will result in a rather verbose error
message indicating the specific problem, such as:

    $ test.py --days 1000
    usage: test.py [-h] [--age AGE] [--ints INTS] [--seconds SECONDS] [--days DAYS]
    test.py: error: argument --days: invalid FloatSequence (from 0 to 365.25), ERROR: "UPPER too large" value: '1000'

Example with *argparse.ArgumentParser*:
---------------------------------------

.. code::

    import argparse
    import tarwalker

    # Note:  Typical values would likely include 'help' and  'default' parameters.
    parser = argparse.ArgumentParser(description="Number printer")

    print(parser.parse_args())

Examples Results:
^^^^^^^^^^^^^^^^^
- would be good.


Known Issues:
-------------
1. For constructing the test data, the tests require the 'pigz' and 'bzip2' programs in the $PATH.

