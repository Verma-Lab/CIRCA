// backend/src/routes/contact.js
import express from 'express';
import nodemailer from 'nodemailer';
const router = express.Router();

const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: 'hritvik2920@gmail.com',
    pass: 'uhrw yogo uwmx rsrr' // Add this to your .env file
  }
});

router.post('/contact', async (req, res) => {
  try {
    const { name, businessName, email, phoneNumber, message } = req.body;

    await transporter.sendMail({
      from: 'hritvik2920@gmail.com',
      to: 'hritvikgupta@tellephon.com',
      subject: `New Contact Form: ${businessName}`,
      html: `
        <div style="padding: 20px; font-family: Arial;">
          <h2>New Contact Form Submission</h2>
          <p><strong>Name:</strong> ${name}</p>
          <p><strong>Business:</strong> ${businessName}</p>
          <p><strong>Email:</strong> ${email}</p>
          <p><strong>Phone:</strong> ${phoneNumber}</p>
          <h3>Message:</h3>
          <p>${message}</p>
        </div>
      `
    });

    res.json({ success: true });
  } catch (error) {
    console.error('Email error:', error);
    res.status(500).json({ success: false, error: 'Failed to send email' });
  }
});

export default router;